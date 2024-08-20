from typing import Optional
from bs4 import BeautifulSoup
import demoji
import emoji
import requests
import json
import yaml
import csv
import regex as re
from model_import import GeneratedMessage, GeneratedMessageType, Prospect, Client
from src.client.models import ClientSDR
from src.li_conversation.autobump_helpers.services_firewall import (
    rule_no_blacklist_words,
)
from src.message_generation.models import GeneratedMessageCTA, GeneratedMessageEmailType
from src.ml.services import detect_hallucinations, get_aree_fix_basic
from src.utils.string.string_utils import (
    has_consecutive_uppercase_string,
)
from app import db, celery

# View experiment here: https://www.notion.so/sellscale/Adversarial-AI-v0-Experiment-901a97de91a845d5a83063f3d6606a4a
ADVERSARIAL_MODEL = "curie:ft-personal-2022-10-27-20-07-22"

# This MUST be changed when the relative path of the csv's changes.
profanity_csv_path = r"src/../datasets/profanity.csv"
web_blacklist_path = r"src/../datasets/web_blacklist.csv"
dr_positions_path = r"src/../datasets/dr_positions.csv"
company_suffix_csv_path = r"src/../datasets/company_suffixes.csv"

SUBJECT_LINE_CHARACTER_LIMIT = 100


def get_adversarial_ai_approval(prompt):
    OPENAI_URL = "https://api.openai.com/v1/completions"

    payload = json.dumps(
        {"model": ADVERSARIAL_MODEL, "prompt": prompt + "\n\n###\n\n", "max_tokens": 1}
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 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",
    }

    raw_response = requests.request(
        "POST", OPENAI_URL, headers=headers, data=payload
    ).text
    response = yaml.safe_load(raw_response)
    choice = response["choices"][0]["text"].strip()

    return choice == "TRUE"


def wipe_problems(message_id: int):
    """Wipe problems for a message. Used to reset the problems for a message to recheck.

    Args:
        message_id (int): The message ID to wipe problems for.
    """
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.problems = []
    message.blocking_problems = []
    message.unknown_named_entities = []
    db.session.add(message)
    db.session.commit()


def format_entities(
    unknown_entities: list,
    problems: list,
    highlighted_words: list,
    whitelisted_names: list = [],
    cta: str = "",
):
    """Formats the unknown entities for the problem message.

    Each unknown entity will appear on its own line.
    """
    lower_whitelisted_names = [name.lower() for name in whitelisted_names]
    cta_lowered = cta.lower()
    if len(unknown_entities) > 0:
        for entity in unknown_entities:
            entity_lowered = entity.lower()

            if (
                entity_lowered == "none"
                or entity_lowered == '"none"'
                or entity_lowered == "'none'"
            ):
                continue

            if (
                entity_lowered not in lower_whitelisted_names
                and entity_lowered not in cta_lowered
            ):
                problems.append("Potential wrong name: '{}'".format(entity))
                highlighted_words.append(entity)
    return


def run_message_rule_engine_on_linkedin_completion(
    completion: str,
    prompt: str,
    run_arree: bool = False,
) -> tuple[str, list, list]:
    """Adversarial AI ruleset for LinkedIn. Only runs on completion so not full-suite of Rules

    Args:
        completion (str): The completion to run the ruleset against.
        prompt (str): The prompt to run the ruleset against.
        run_arree (bool, optional): Whether to run the ARREE autocorrect. Defaults to False.

    Returns:
        tuple[str, list, list, list]: The completion, problems, blocking_problems, and highlighted_words.
    """
    prompt = ""
    problems = []
    blocking_problems = []
    highlighted_words = []

    case_preserved_completion = completion
    completion = completion.lower()

    # Strict Rules
    rule_no_profanity(
        completion=completion,
        problems=problems,
        blocking_problems=blocking_problems,
        highlighted_words=highlighted_words,
    )
    rule_no_url(completion, problems, highlighted_words)
    rule_linkedin_length(
        message_type=GeneratedMessageType.LINKEDIN,
        completion=completion,
        problems=problems,
        blocking_problems=blocking_problems,
        highlighted_words=highlighted_words,
    )
    rule_no_brackets(
        completion=completion,
        problems=problems,
        blocking_problems=blocking_problems,
        highlighted_words=highlighted_words,
    )

    # Warnings
    rule_no_cookies(completion, problems, highlighted_words)
    rule_no_symbols(completion, problems, highlighted_words)
    rule_no_companies(completion, problems, highlighted_words)
    rule_catch_strange_titles(completion, prompt, problems, highlighted_words)
    rule_no_hard_years(completion, prompt, problems, highlighted_words)
    # rule_catch_im_a(completion, prompt, problems, highlighted_words)
    # rule_catch_no_i_have(completion, prompt, problems, highlighted_words)
    rule_catch_has_6_or_more_consecutive_upper_case(
        case_preserved_completion, prompt, problems, highlighted_words
    )
    # rule_no_ampersand(completion, problems, highlighted_words)
    rule_no_fancying_a_chat(completion, problems, highlighted_words)
    # rule_no_ingratiation(completion, problems, highlighted_words)

    if run_arree:
        completion = get_aree_fix_basic(completion=completion, problems=problems)

    return completion, problems, blocking_problems, highlighted_words


def run_message_rule_engine(message_id: int):
    """Adversarial AI ruleset.

    Args:
        message_id (int): The message ID to run the ruleset against.

    Returns:
        bool: Whether the message passes the ruleset.
    """
    # Wipe problems before running the ruleset
    wipe_problems(message_id)

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    if message.message_cta:
        cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(message.message_cta)
    else:
        cta = None
    prompt = message.prompt
    case_preserved_completion = message.completion
    completion = message.completion.lower()

    # If the message is an email, we need to strip the HTML tags
    if message.message_type == GeneratedMessageType.EMAIL:
        # Add spaces between HTML tags
        completion = re.sub(r">", "> ", completion)

        # Remove HTML tags
        soup = BeautifulSoup(completion, "html.parser")

        # Get the text without HTML tags
        completion = soup.get_text()

    prospect: Prospect = Prospect.query.get(message.prospect_id)
    prospect_name = prospect.full_name
    client_id = prospect.client_id
    client_sdr_id = prospect.client_sdr_id
    client: Client = Client.query.get(client_id)
    client_name = client.company
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    whitelisted_names = [client_name, client_sdr.name]

    problems = []
    blocking_problems = []
    highlighted_words = []

    # Hallucination check for Linkedin only
    # if message.message_type == GeneratedMessageType.LINKEDIN:
    #     rule_no_hallucinations(
    #         message_id=message_id,
    #         problems=problems,
    #         blocking_problems=blocking_problems,
    #         highlighted_words=highlighted_words,
    #     )

    # Strict Rules
    rule_no_profanity(
        completion=completion,
        problems=problems,
        blocking_problems=blocking_problems,
        highlighted_words=highlighted_words,
    )
    # rule_no_url(completion, problems, highlighted_words)
    rule_linkedin_length(
        message_type=message.message_type,
        completion=completion,
        problems=problems,
        blocking_problems=blocking_problems,
        highlighted_words=highlighted_words,
    )
    if (
        message.message_type == GeneratedMessageType.LINKEDIN
    ):  # Only apply this rule to LinkedIn messages
        rule_address_doctor(
            prompt, completion, problems, highlighted_words, prospect_name
        )
    rule_no_brackets(
        completion=completion,
        problems=problems,
        blocking_problems=blocking_problems,
        highlighted_words=highlighted_words,
    )

    # Warnings
    rule_no_cookies(completion, problems, highlighted_words)
    rule_no_symbols(completion, problems, highlighted_words, message.message_type)
    rule_no_companies(completion, problems, highlighted_words)
    rule_catch_strange_titles(completion, prompt, problems, highlighted_words)
    rule_no_hard_years(completion, prompt, problems, highlighted_words)
    # rule_catch_im_a(completion, prompt, problems, highlighted_words)
    # rule_catch_no_i_have(completion, prompt, problems, highlighted_words)

    if message.message_type != GeneratedMessageType.EMAIL:
        rule_catch_has_6_or_more_consecutive_upper_case(
            case_preserved_completion, prompt, problems, highlighted_words
        )
    # rule_no_ampersand(completion, problems, highlighted_words)
    rule_no_fancying_a_chat(completion, problems, highlighted_words)

    # if message.message_type != GeneratedMessageType.EMAIL:
    #     rule_no_ingratiation(completion, problems, highlighted_words)

    rule_no_sdr_blacklist_words(
        completion=completion,
        problems=problems,
        blocking_problems=blocking_problems,
        highlighted_words=highlighted_words,
        client_sdr_id=client_sdr_id,
    )

    # Only run for Email Subject Lines
    if (
        message.message_type == GeneratedMessageType.EMAIL
        and message.email_type == GeneratedMessageEmailType.SUBJECT_LINE
    ):
        rule_subject_line_character_limit(
            completion=completion,
            problems=problems,
            blocking_problems=blocking_problems,
        )

    # Only run for linkedin:
    if message.message_type == GeneratedMessageType.LINKEDIN:
        if " me " in completion:
            problems.append("Contains 'me'.")
            highlighted_words.append("me")

        if "they've worked " in completion:
            problems.append("Contains 'they've worked'.")
            highlighted_words.append("they've worked")

        if "i've spent" in completion:
            problems.append("Contains 'i've spent'.")
            highlighted_words.append("i've spent")

        if "stealth" in completion:
            problems.append(
                "Contains 'stealth'. Check if they are referring to a past job."
            )
            highlighted_words.append("stealth")

    highlighted_words = list(filter(lambda x: x != ".", highlighted_words))

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.problems = problems
    message.blocking_problems = blocking_problems
    message.highlighted_words = highlighted_words
    db.session.add(message)
    db.session.commit()

    # only run autocorrect for Linkedin
    if message.message_type == GeneratedMessageType.LINKEDIN:
        run_autocorrect(message_id)

    return problems


def run_autocorrect(message_id: int):
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    if message.autocorrect_run_count is not None and message.autocorrect_run_count > 0:
        return
    if (
        message.before_autocorrect_text
        or message.after_autocorrect_text
        or message.before_autocorrect_problems
    ):
        return

    # todo(Aakash) eventually enable this for both Linkedin and Email. For now, only run for Linkedin
    # if message.message_type != GeneratedMessageType.LINKEDIN:
    #     return

    before_autocorrect_text = message.completion
    before_autocorrect_problems = message.problems

    if len(message.problems) > 0:
        after_autocorrect_text = get_aree_fix_basic(message_id)

        correction_tries = 1
        while correction_tries < 3 and not after_autocorrect_text:
            after_autocorrect_text = get_aree_fix_basic(message_id)
            correction_tries = correction_tries + 1
    else:
        after_autocorrect_text = message.completion

    message.autocorrect_run_count = (
        message.autocorrect_run_count + 1 if message.autocorrect_run_count else 1
    )
    message.before_autocorrect_text = before_autocorrect_text
    message.before_autocorrect_problems = before_autocorrect_problems
    message.after_autocorrect_text = after_autocorrect_text
    message.completion = after_autocorrect_text
    db.session.add(message)
    db.session.commit()

    run_message_rule_engine(message_id)


def rule_no_hallucinations(
    message_id: int,
    problems: list,
    blocking_problems: list,
    highlighted_words: list,
):
    """Rule (blocking): No Hallucinations

    No hallucinations allowed in the completion.
    """
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    hallucinations = detect_hallucinations(
        message_prompt=(
            message.few_shot_prompt if message.few_shot_prompt else message.prompt
        ),
        message=message.completion,
    )
    if hallucinations and len(hallucinations) > 0:
        problems.append("Contains hallucinations: {}".format(", ".join(hallucinations)))
        blocking_problems.append(
            "Contains hallucinations: {}".format(", ".join(hallucinations))
        )
        highlighted_words.extend(hallucinations)

    return


def rule_no_symbols(
    completion: str,
    problems: list,
    highlighted_words: list,
    message_type: Optional[GeneratedMessageType] = None,
):
    """Rule (non-blocking): No Symbols

    No symbols allowed in the completion.

    \p{S} matches any math symbols, currency signs, dingbats, box-drawing characters, etc
    """
    ALLOWED_SYMBOLS = ["+", "$", "|"]
    if message_type == GeneratedMessageType.EMAIL:
        ALLOWED_SYMBOLS.extend(["@", "<", ">"])

    completion = demoji.replace(completion, "")  # Remove emojis
    unfiltered_match = re.findall(r"[\p{S}]", completion)
    match = list(filter(lambda x: x not in ALLOWED_SYMBOLS, unfiltered_match))
    if match and len(match) > 0:
        problems.append(
            "Completion contains uncommon symbols: {}".format(", ".join(match))
        )

    return


def rule_no_sdr_blacklist_words(
    completion: str,
    problems: list,
    blocking_problems: list,
    highlighted_words: list,
    client_sdr_id: int,
):
    """Rule (blocking): No SDR Blacklist Words

    No SDR blacklist words allowed in the completion.
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    blacklist_words = client_sdr.blacklisted_words
    if not blacklist_words or len(blacklist_words) == 0:
        return

    # Check the message for blacklist words
    detected_blacklist_words = []
    for word in completion.split():
        stripped_word = re.sub(
            "[^0-9a-zA-Z]+",
            "",
            word,
        ).strip()
        if word.lower() in blacklist_words:
            detected_blacklist_words.append("'" + word + "'")
        elif stripped_word.lower() in blacklist_words:
            detected_blacklist_words.append("'" + stripped_word + "'")

    if detected_blacklist_words:
        problems.append(
            "Message contains a blacklisted phrase: "
            + ", ".join(detected_blacklist_words)
            + " Please rephrase without these phrases."
        )
        blocking_problems.append(
            "Message contains a blacklisted phrase: "
            + ", ".join(detected_blacklist_words)
            + " Please rephrase without these phrases."
        )
        highlighted_words.extend(detected_blacklist_words)

    return


def rule_address_doctor(
    prompt: str,
    completion: str,
    problems: list,
    highlighted_words: list,
    prospect_name: str,
):
    """Rule (non-blocking): Address Doctor

    The completion must address the doctor.
    """

    # Grab the title and name section.
    title_section = ""
    name_section = ""
    for section in prompt.split("<>"):
        if section.startswith("title:"):
            title_section = section.lower()
        if section.startswith("name:"):
            name_section = section.lower()

    # Check if the title and name section contains a doctor title or 'MD'.
    with open(dr_positions_path, newline="") as f:
        reader = csv.reader(f)
        dr_positions = set()
        dr_assistant_positions = set()
        for row in reader:
            dr_positions.add(row[0])
            if len(row) > 1:
                dr_assistant_positions.add(row[1].strip())

        title_splitted = title_section.split(" ")
        name_splitted = name_section.split(" ")
        for position, title in enumerate(title_splitted):
            if title in dr_positions and "dr." not in completion:
                if position + 1 < len(title_splitted):
                    if title_splitted[position + 1] in dr_assistant_positions:
                        continue
                problems.append(
                    f"The subject should be addressed as a Doctor. The subject's name is: {prospect_name}"
                )
                highlighted_words.extend(name_splitted)
                return

        title_search = re.search(
            "[^a-zA-Z][mM][.]?[dD][.]?[^a-zA-Z]?",
            title_section,
        )
        if title_search is not None and "dr." not in completion:
            problems.append(
                f"The subject should be addressed as a Doctor. The subject's name is: {prospect_name}"
            )
            highlighted_words.extend(name_splitted)
            return

        for name in name_splitted:
            if name in dr_positions and "dr." not in completion:
                problems.append(
                    f"The subject should be addressed as a Doctor. The subject's name is: {prospect_name}"
                )
                highlighted_words.extend(name_splitted)
                return

        name_search = re.search(
            "[^a-zA-Z][mM][.]?[dD][.]?[^a-zA-Z]?",
            name_section,
        )
        if name_search is not None and "dr." not in completion:
            problems.append(
                f"The subject should be addressed as a Doctor. The subject's name is: {prospect_name}"
            )
            highlighted_words.extend(name_splitted)
            return

    return


def rule_no_profanity(
    completion: str, problems: list, blocking_problems: list, highlighted_words: list
):
    """Rule (blocking): No Profanity

    No profanity allowed in the completion.
    """
    with open(profanity_csv_path, newline="") as f:
        reader = csv.reader(f)
        profanity = set([row[0] for row in reader])

    detected_profanities = []
    for word in completion.split():
        stripped_word = re.sub(
            "[^0-9a-zA-Z]+",
            "",
            word,
        ).strip()
        if word in profanity:
            detected_profanities.append("'" + word + "'")
        elif stripped_word in profanity:
            detected_profanities.append("'" + stripped_word + "'")

    if len(detected_profanities) > 0:
        problem_string = ", ".join(detected_profanities)
        problems.append("Contains profanity: {}".format(problem_string))
        blocking_problems.append("Contains profanity: {}".format(problem_string))

        words = problem_string.split(", ")
        for word in words:
            highlighted_words.append(word.replace("'", ""))

    return


def rule_no_cookies(completion: str, problems: list, highlighted_words: list):
    """Rule (non-blocking): No Cookies!

    No cookies, or any other web related things, allowed in the completion.
    """
    with open(web_blacklist_path, newline="") as f:
        reader = csv.reader(f)
        web_blacklist = set([row[0] for row in reader])

    detected_cookies = []
    for word in completion.split():
        stripped_word = re.sub(
            "[^0-9a-zA-Z]+",
            "",
            word,
        ).strip()
        if word in web_blacklist:
            detected_cookies.append("'" + word + "'")
        elif stripped_word in web_blacklist:
            detected_cookies.append("'" + stripped_word + "'")

    if len(detected_cookies) > 0:
        problem_string = ", ".join(detected_cookies)
        problems.append(
            "Contains web related words: {}. Please check for relevance.".format(
                problem_string
            )
        )
        words = problem_string.split(", ")
        for word in words:
            highlighted_words.append(word.replace("'", ""))

    return


def rule_no_url(completion: str, problems: list, highlighted_words: list):
    """Rule (non-blocking): No URL

    No URL's allowed in the completion.
    """
    if "www." in completion:
        problems.append("Contains a URL.")
        highlighted_words.append("www.")

    return


def rule_linkedin_length(
    message_type: GeneratedMessageType,
    completion: str,
    problems: list,
    blocking_problems: list,
    highlighted_words: list,
):
    """Rule (blocking): Linkedin Length

    Linkedin messages must be less than 300 characters.
    """
    if message_type == GeneratedMessageType.LINKEDIN and len(completion) > 300:
        problems.append("The message is too long. Make the message about half as long.")
        blocking_problems.append(
            "The message is too long. Make the message about half as long."
        )

    return


def rule_no_companies(completion: str, problems: list, highlighted_words: list):
    """Rule (non-blocking): No companies

    No company abbreviations allowed in the completion. ie 'LLC', 'Inc.'
    """
    with open(company_suffix_csv_path, newline="") as f:
        reader = csv.reader(f)
        company_suffixes = set([row[0] for row in reader])

    detected_abbreviations = []
    for word in completion.split():
        stripped_word = re.sub(
            "[^0-9a-zA-Z]+",
            "",
            word,
        ).strip()
        if stripped_word in company_suffixes:
            highlighted_words.append(stripped_word)
            detected_abbreviations.append(stripped_word)

    if len(detected_abbreviations) > 0:
        problem_string = ", ".join(detected_abbreviations)
        problems.append(
            "Contains overly-formal company name: '{}'. Remove if possible.".format(
                problem_string
            )
        )

    return


def rule_catch_strange_titles(
    completion: str, prompt: str, problems: list, highlighted_words: list
):
    """Rule (non-blocking): Catch Strange Titles

    Catch titles that are too long.
    """
    title_section_case_preserved = ""
    title_section = ""
    for section in prompt.split("<>"):
        if section.startswith("title:"):
            title_section = (
                section.lower().split("title:")[1].strip()
            )  # Get everything after 'title:'
            title_section_case_preserved = section.split("title:")[1].strip()

    if title_section == "":  # No title, no problem
        return

    # Abbreviations are permissable
    roles = {
        "chief executive officer": "ceo",
        "chief financial officer": "cfo",
        "chief technology officer": "cto",
        "chief marketing officer": "cmo",
        "chief operating officer": "coo",
        "chief information officer": "cio",
        "chief technical officer": "cto",
        "chief data officer": "cdo",
        "chief product officer": "cpo",
        "chief revenue officer": "cro",
        "chief security officer": "cso",
        "chief legal officer": "clo",
        "chief analytics officer": "cao",
        "chief compliance officer": "cco",
        "chief human resources officer": "chro",
        "chief information security officer": "ciso",
        "chief quality officer": "cqo",
        "chief visionary officer": "cvo",
        "chief business officer": "cbo",
        "chief creative officer": "cco",
        "chief investment officer": "cio",
        "chief medical officer": "cmo",
    }
    lower_title = title_section.lower()
    if "chief" in lower_title and "officer" in lower_title:
        chief_index = lower_title.find("chief")
        officer_index = lower_title.find("officer")
        if chief_index < officer_index:
            title = title_section[chief_index : officer_index + 1]
            if title in roles:
                if roles[title] in completion.lower():
                    return

    splitted_title_section = title_section.split(" ")
    # if len(splitted_title_section) >= 4:
    #     first_words = splitted_title_section[:4]  # Get the first 4 words
    #     first_words = " ".join(first_words).strip()
    #     if first_words in completion.lower():  # 4 words is too long for a title
    #         first_words_case_preserved = title_section_case_preserved.split(" ")[:4]
    #         first_words_case_preserved = " ".join(first_words_case_preserved).strip()
    #         highlighted_words.append(first_words_case_preserved)
    #         problems.append(
    #             "WARNING: Prospect's job title may be too long. Please simplify it to sound more natural. (e.g. VP Growth and Marketing → VP Marketing)"
    #         )
    #         return
    # else:

    if title_section in completion.lower():
        ALLOWED_SYMBOLS = ["'"]
        unfiltered_match = re.findall(r"[\p{S}\p{P}]", title_section)
        match = list(filter(lambda x: x not in ALLOWED_SYMBOLS, unfiltered_match))
        if match and len(match) > 0:
            highlighted_words.append(title_section_case_preserved)
            problems.append(
                "WARNING: Prospect's job title contains strange symbols. Please remove any strange symbols."
            )

    return


def rule_no_hard_years(
    completion: str, prompt: str, problems: list, highlighted_words: list
):
    """Rule (non-blocking): No Hard Years

    If 'decade' is in the prompt, then 'years' should not be in the completion.

    Also attempts to catch colloquial years. (e.g. 6 months → half a year, 5 years → half a decade)

    This heuristic is imperfect.
    """
    # Sometimes "decade" will not directly influence the completion, in which case we don't want using "years" to be a problem.
    # if "decade" in prompt:
    #     if "decade" not in completion and "years" in completion:
    #         problems.append(
    #             "A hard number year may appear non-colloquial. Reference the number without using a digit. Use references to decades if possible."
    #         )

    #         # Highlight the word 'years' and the word before it. Imperfect heurstic, may need change.
    #         splitted = completion.split()
    #         for i in range(len(splitted)):
    #             word = splitted[i]
    #             if word == "years":
    #                 highlighted_words.append(splitted[i - 1] + " " + word)
    #                 break
    #     return

    # Catch colloquial years that should be rounded.
    if "nine years" in completion:
        problems.append(
            "'nine years' is non-colloquial. Please use 'nearly a decade' instead."
        )
        highlighted_words.append("nine years")
    elif "eight years" in completion:
        problems.append(
            "'eight years' is non-colloquial. Please use 'nearly a decade' instead."
        )
        highlighted_words.append("eight years")
    elif "6 months" in completion:
        problems.append(
            "'6 months' is non-colloquial. Please use 'half a year' instead."
        )
        highlighted_words.append("6 months")

    # Catch hard years
    if "years" in completion:
        # Highlight the word 'years' and the word before it. Imperfect heurstic, may need change.
        splitted = completion.split()
        for i in range(len(splitted)):
            word = splitted[i]
            if word == "years":
                year = splitted[i - 1]
                if year.isdigit():
                    problems.append(
                        "A hard number year may appear non-colloquial. Reference the number without using a digit."
                    )
                    highlighted_words.append(year + " " + word)
                    break

    return


# DEPRECATED [2024-03-25]: LLMs have become much better at sounding genuine. This rule is no longer necessary.
# def rule_catch_im_a(
#     completion: str, prompt: str, problems: list, highlighted_words: list
# ):
#     """NO BLOCK Rule: Catch 'I'm a'

#     Catch 'I'm a' in the completion.
#     """
#     if "i'm a" in prompt.lower():
#         return

#     if re.search(r"i'm a ", completion.lower()):
#         if (
#             "big" not in completion.lower()
#             and "massive" not in completion.lower()
#             and "huge" not in completion.lower()
#             and "fan" not in completion.lower()
#         ):
#             problems.append(
#                 'Found "I\'m a" in the completion. Ensure that the completion is not making false claims.'
#             )
#             highlighted_words.append("I'm a")

#     return


# DEPRECATED [2024-03-25]: LLMs have become much better at sounding genuine. This rule is no longer necessary.
# def rule_catch_no_i_have(
#     completion: str, prompt: str, problems: list, highlighted_words: list
# ):
#     """Rule: Catch 'I have'

#     Catch 'I have' in the completion.
#     """
#     if "i have " in completion and (
#         completion.find("i have") == 0
#         or completion[completion.find("i have") - 1] == " "
#     ):
#         problems.append("Uses first person 'I have'.")
#         highlighted_words.append("i have")


# DEPRECATED [2024-03-25]: LLMs have become much better at sounding genuine. This rule is no longer necessary.
# def rule_no_ingratiation(completion: str, problems: list, highlighted_words: list):
#     """Rule: No Ingratiation

#     No ingratiation allowed in the completion.
#     """
#     ingratiating_words = [
#         "impressive",
#         "truly",
#     ]

#     for word in ingratiating_words:
#         if word in completion:
#             problems.append(
#                 f"Contains ingratiating phrase: '{word}'. Avoid using this phrase."
#             )
#             highlighted_words.append(word)


def rule_catch_has_6_or_more_consecutive_upper_case(
    completion: str, prompt: str, problems: list, highlighted_words: list
):
    """Rule (non-blocking): Catch 6 or more consecutive upper case letters

    Catch 6 or more consecutive upper case letters in the completion.
    """
    has_long_str, long_str = has_consecutive_uppercase_string(completion, 6)
    if has_long_str:
        problems.append(
            f"Contains long, uppercase word(s): '{long_str}'. Please fix capitalization, if applicable."
        )
        highlighted_words.append(long_str)


def rule_no_ampersand(completion: str, problems: list, highlighted_words: list):
    """Rule (non-blocking): No Ampersand

    As a general rule of thumb, an Ampersand (&) is most likely not used by a human writer.

    In the case where an Ampersand appears, it should be double checked. Company names with ampersands are rare and warrant review.
    """
    if "&" in completion:
        problems.append(
            "Contains an ampersand (&). Please double check that this is correct."
        )
        highlighted_words.append("&")


def rule_no_brackets(
    completion: str, problems: list, blocking_problems: list, highlighted_words: list
):
    """Rule (blocking): No Brackets

    No brackets allowed in the completion.
    """
    if "[" in completion or "]" in completion or "{" in completion or "}" in completion:
        # problems.append("Contains brackets. Please remove all brackets or replace value in brackets with appropriate value.")
        problems.append("Contains brackets.")
        blocking_problems.append("Contains brackets.")
        highlighted_words.append("[")
        highlighted_words.append("]")
        highlighted_words.append("{")
        highlighted_words.append("}")

    return


def rule_no_fancying_a_chat(completion: str, problems: list, highlighted_words: list):
    """Rule: No Fancying a Chat

    No 'fancy a chat' allowed in the completion.
    """
    if "fancy a chat" in completion:
        problems.append(
            "Contains 'fancy a chat'. Do not use this phrase in the completions. Do not use the word 'fancy' in the completion."
        )
        highlighted_words.append("fancy a")

    return


def rule_subject_line_character_limit(
    completion: str, problems: list, blocking_problems: list
):
    """Rule (blocking): Subject Line Character Limit

    Subject line must be less than a character limit.
    """
    if len(completion) > SUBJECT_LINE_CHARACTER_LIMIT:
        problems.append("Subject line is too long. Please shorten it.")
        blocking_problems.append("Subject line is too long. Please shorten it.")

    return
