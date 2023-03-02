import requests
import json
import csv
import regex as re
from model_import import GeneratedMessage, GeneratedMessageType, Prospect, Client
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
company_abbrev_csv_path = r"src/../datasets/company_abbreviations.csv"


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
    response = json.loads(raw_response)
    choice = response["choices"][0]["text"].strip()

    return choice == "TRUE"


def wipe_problems(message_id: int):
    """Wipe problems for a message. Used to reset the problems for a message to recheck.

    Args:
        message_id (int): The message ID to wipe problems for.
    """
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.problems = []
    message.unknown_named_entities = []
    db.session.add(message)
    db.session.commit()


def format_entities(
    unknown_entities: list,
    problems: list,
    highlighted_words: list,
    whitelisted_names: list = [],
):
    """Formats the unknown entities for the problem message.

    Each unknown entity will appear on its own line.
    """
    lower_whitelisted_names = [name.lower() for name in whitelisted_names]
    if len(unknown_entities) > 0:
        for entity in unknown_entities:
            if entity.lower() not in lower_whitelisted_names:
                problems.append("Potential wrong name: '{}'".format(entity))
                highlighted_words.append(entity)
    return


def run_message_rule_engine(message_id: int):
    """Adversarial AI ruleset.

    Args:
        message_id (int): The message ID to run the ruleset against.

    Returns:
        bool: Whether the message passes the ruleset.
    """
    from src.message_generation.services import (
        run_check_message_has_bad_entities,
    )

    wipe_problems(message_id)

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    prompt = message.prompt
    case_preserved_completion = message.completion
    completion = message.completion.lower()

    prospect: Prospect = Prospect.query.get(message.prospect_id)
    client_id = prospect.client_id
    client: Client = Client.query.get(client_id)
    client_name = client.company
    whitelisted_names = [client_name]

    problems = []
    highlighted_words = []

    # NER AI
    run_check_message_has_bad_entities(message_id)
    format_entities(
        message.unknown_named_entities, problems, highlighted_words, whitelisted_names
    )

    # Strict Rules
    rule_no_profanity(completion, problems, highlighted_words)
    rule_no_url(completion, problems, highlighted_words)
    rule_linkedin_length(message.message_type, completion, problems, highlighted_words)
    rule_address_doctor(prompt, completion, problems, highlighted_words)

    # Warnings
    rule_no_cookies(completion, problems, highlighted_words)
    rule_no_symbols(completion, problems, highlighted_words)
    rule_no_companies(completion, problems, highlighted_words)
    rule_catch_strange_titles(completion, prompt, problems, highlighted_words)
    rule_no_hard_years(completion, prompt, problems, highlighted_words)
    rule_catch_im_a(completion, prompt, problems, highlighted_words)
    rule_catch_no_i_have(completion, prompt, problems, highlighted_words)
    rule_catch_has_6_or_more_consecutive_upper_case(
        case_preserved_completion, prompt, problems, highlighted_words
    )

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
    message.highlighted_words = highlighted_words
    db.session.add(message)
    db.session.commit()

    return problems


def rule_no_symbols(completion: str, problems: list, highlighted_words: list):
    """Rule: No Symbols

    No symbols allowed in the completion.

    \p{S} matches any math symbols, currency signs, dingbats, box-drawing characters, etc
    """
    ALLOWED_SYMBOLS = ["+"]
    unfiltered_match = re.findall(r"[\p{S}]", completion)
    match = list(filter(lambda x: x not in ALLOWED_SYMBOLS, unfiltered_match))
    if match and len(match) > 0:
        problems.append(
            "Completion contains uncommon symbols: {}".format(", ".join(match))
        )

    return


def rule_address_doctor(
    prompt: str, completion: str, problems: list, highlighted_words: list
):
    """Rule: Address Doctor

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
        dr_positions = set([row[0] for row in reader])

        title_splitted = title_section.split(" ")
        name_splitted = name_section.split(" ")
        for title in title_splitted:
            if title in dr_positions and "dr." not in completion:
                problems.append(
                    "Title contains a doctor position '{}' but no 'Dr.' in message".format(
                        title
                    )
                )
                highlighted_words.extend(name_splitted)
                return

        title_search = re.search(
            "[^a-zA-Z][mM][.]?[dD][.]?[^a-zA-Z]?",
            title_section,
        )
        if title_search is not None and "dr." not in completion:
            problems.append("Title contains 'MD' but no 'Dr.' in message")
            highlighted_words.extend(name_splitted)
            return

        for name in name_splitted:
            if name in dr_positions and "dr." not in completion:
                problems.append(
                    "Name contains a doctor position '{}' but no 'Dr.' in message".format(
                        name
                    )
                )
                highlighted_words.extend(name_splitted)
                return

        name_search = re.search(
            "[^a-zA-Z][mM][.]?[dD][.]?[^a-zA-Z]?",
            name_section,
        )
        if name_search is not None and "dr." not in completion:
            problems.append("Name contains 'MD' but no 'Dr.' in message")
            highlighted_words.extend(name_splitted)
            return

    return


def rule_no_profanity(completion: str, problems: list, highlighted_words: list):
    """Rule: No Profanity

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

        words = problem_string.split(", ")
        for word in words:
            highlighted_words.append(word.replace("'", ""))

    return


def rule_no_cookies(completion: str, problems: list, highlighted_words: list):
    """Rule: No Cookies!

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
    """Rule: No URL

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
    highlighted_words: list,
):
    """Rule: Linkedin Length

    Linkedin messages must be less than 300 characters.
    """
    if message_type == GeneratedMessageType.LINKEDIN and len(completion) > 300:
        problems.append("LinkedIn message is > 300 characters.")

    return


def rule_no_companies(completion: str, problems: list, highlighted_words: list):
    """Rule: No companies

    No company abbreviations allowed in the completion. ie 'LLC', 'Inc.'
    """
    with open(company_abbrev_csv_path, newline="") as f:
        reader = csv.reader(f)
        company_abbreviations = set([row[0] for row in reader])

    detected_abbreviations = []
    for word in completion.split():
        stripped_word = re.sub(
            "[^0-9a-zA-Z]+",
            "",
            word,
        ).strip()
        if stripped_word in company_abbreviations:
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
    """Rule: Catch Strange Titles

    Catch titles that are too long.
    """
    title_section = ""
    for section in prompt.split("<>"):
        if section.startswith("title:"):
            title_section = (
                section.lower().split("title:")[1].strip()
            )  # Get everything after 'title:'
            title_section_case_preserved = section.split("title:")[1].strip()

    if title_section == "":  # No title, no problem
        return

    splitted_title_section = title_section.split(" ")
    if len(splitted_title_section) >= 4:
        first_words = splitted_title_section[:4]  # Get the first 4 words
        first_words = " ".join(first_words).strip()
        if first_words in completion.lower():  # 4 words is too long for a title
            first_words_case_preserved = title_section_case_preserved.split(" ")[:4]
            first_words_case_preserved = " ".join(first_words_case_preserved).strip()
            highlighted_words.append(first_words_case_preserved)
            problems.append(
                "WARNING: Prospect's job title may be too long. Please simplify it to sound more natural. (e.g. VP Growth and Marketing → VP Marketing)"
            )
            return
    else:
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
    """Rule: No Hard Years

    If 'decade' is in the prompt, then 'years' should not be in the completion.

    This heuristic is imperfect.
    """
    if "decade" in prompt:
        if "decade" not in completion and "years" in completion:
            problems.append(
                "Please reference years in colloquial terms. (e.g. 5 years → half a decade)"
            )

            # Highlight the word 'years' and the word before it. Imperfect heurstic, may need change.
            splitted = completion.split()
            for i in range(len(splitted)):
                word = splitted[i]
                if word == "years":
                    highlighted_words.append(splitted[i - 1] + " " + word)
                    break

    return


def rule_catch_im_a(
    completion: str, prompt: str, problems: list, highlighted_words: list
):
    """Rule: Catch 'I'm a'

    Catch 'I'm a' in the completion.
    """
    if "i'm a" in prompt.lower():
        return
    if (
        "i'm a" in completion.lower()
        and "big" not in completion.lower()
        and "massive" not in completion.lower()
        and "huge" not in completion.lower()
        and "fan" not in completion.lower()
    ):
        problems.append(
            'Found "I\'m a" in the completion. Ensure that the completion is not making false claims.'
        )
        highlighted_words.append("I'm a")

    return


def rule_catch_no_i_have(
    completion: str, prompt: str, problems: list, highlighted_words: list
):
    """Rule: Catch 'I have'

    Catch 'I have' in the completion.
    """
    if "i have " in completion and (
        completion.find("i have") == 0
        or completion[completion.find("i have") - 1] == " "
    ):
        problems.append("Uses first person 'I have'.")
        highlighted_words.append("i have")


def rule_catch_has_6_or_more_consecutive_upper_case(
    completion: str, prompt: str, problems: list, highlighted_words: list
):
    """Rule: Catch 6 or more consecutive upper case letters

    Catch 6 or more consecutive upper case letters in the completion.
    """
    has_long_str, long_str = has_consecutive_uppercase_string(completion, 6)
    if has_long_str:
        problems.append(
            "Contains a long, uppercase word. Verify that names are capitalized correctly."
        )
        highlighted_words.append(long_str)
