import requests
import json
import csv
import regex as re
from model_import import GeneratedMessage, GeneratedMessageType
from app import db, celery

# View experiment here: https://www.notion.so/sellscale/Adversarial-AI-v0-Experiment-901a97de91a845d5a83063f3d6606a4a
ADVERSARIAL_MODEL = "curie:ft-personal-2022-10-27-20-07-22"

# This MUST be changed when the relative path of the csv's changes.
profanity_csv_path = r"src/../datasets/profanity.csv"
web_blacklist_path = r"src/../datasets/web_blacklist.csv"
dr_positions_path = r"src/../datasets/dr_positions.csv"


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


def format_entities(unknown_entities: list, problems: list):
    """Formats the unknown entities for the problem message.

    Each unknown entity will appear on its own line.
    """
    if len(unknown_entities) > 0:
        for entity in unknown_entities:
            problems.append("Potential wrong name: '{}'".format(entity))
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
    completion = message.completion.lower()

    problems = []

    # NER AI
    run_check_message_has_bad_entities(message_id)
    format_entities(message.unknown_named_entities, problems)

    # Strict Rules
    rule_no_profanity(completion, problems)
    rule_no_url(completion, problems)
    rule_linkedin_length(message.message_type, completion, problems)
    rule_address_doctor(prompt, completion, problems)

    # Warnings
    rule_no_cookies(completion, problems)
    rule_no_symbols(completion, problems)

    if "i have " in completion:
        problems.append("Uses first person 'I have'.")

    if " me " in completion:
        problems.append("Contains 'me'.")

    if "they've worked " in completion:
        problems.append("Contains 'they've worked'.")

    if "i've spent" in completion:
        problems.append("Contains 'i've spent'.")

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.problems = problems
    db.session.add(message)
    db.session.commit()

    return problems


def rule_no_symbols(completion: str, problems: list):
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


def rule_address_doctor(prompt: str, completion: str, problems: list):
    """Rule: Address Doctor

    The completion must address the doctor.
    """
    search = re.search(
        "[^a-zA-Z]?[mM][.]?[dD][^a-zA-Z]?",
        prompt,
    )

    if search is not None and "dr." not in completion:
        problems.append("Prompt contains 'MD' but no 'Dr.' in message")
        return

    # Look in the title for position which implies a doctor
    title_section = ''
    for section in prompt.split('<>'):
        if section.startswith('title:'):
            title_section = section.lower()
    with open(dr_positions_path, newline="") as f:
        reader = csv.reader(f)
        dr_positions = set([row[0] for row in reader])
        title_splitted = title_section.split(' ')
        for title in title_splitted:
            if title in dr_positions and "dr." not in completion:
                problems.append("Prompt contains a doctor position '{}' but no 'Dr.' in message".format(title))
                return
                
    return


def rule_no_profanity(completion: str, problems: list):
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

    return


def rule_no_cookies(completion: str, problems: list):
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

    return


def rule_no_url(completion: str, problems: list):
    """Rule: No URL

    No URL's allowed in the completion.
    """
    if "www." in completion:
        problems.append("Contains a URL.")

    return


def rule_linkedin_length(
    message_type: GeneratedMessageType, completion: str, problems: list
):
    """Rule: Linkedin Length

    Linkedin messages must be less than 300 characters.
    """
    if message_type == GeneratedMessageType.LINKEDIN and len(completion) > 300:
        problems.append("LinkedIn message is > 300 characters.")

    return
