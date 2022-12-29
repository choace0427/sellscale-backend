import requests
import json
import csv
from model_import import GeneratedMessage, GeneratedMessageType
from app import db, celery

# View experiment here: https://www.notion.so/sellscale/Adversarial-AI-v0-Experiment-901a97de91a845d5a83063f3d6606a4a
ADVERSARIAL_MODEL = "curie:ft-personal-2022-10-27-20-07-22"

# This MUST be changed when the relative path of the profanity changes.
profanity_csv_path = r'src/../datasets/profanity.csv'

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

    # General Rules
    rule_no_profanity(completion, problems)
    rule_no_url(completion, problems)

    if "i have " in completion:
        problems.append("Uses first person 'I have'.")

    if " me " in completion:
        problems.append("Contains 'me'.")

    if "MD" in prompt and "Dr" not in completion:
        problems.append("Contains 'MD' but not 'Dr'. in title")

    if "they've worked " in completion:
        problems.append("Contains 'they've worked'.")

    if "i've spent" in completion:
        problems.append("Contains 'i've spent'.")

    if (
        len(completion) > 300
        and message.message_type == GeneratedMessageType.LINKEDIN
    ):
        problems.append("Linkedin message is > 300 characters.")

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.problems = problems
    db.session.add(message)
    db.session.commit()

    return problems


def format_entities(unknown_entities: list, problems: list):
    """ Formats the unknown entities for the problem message.

    Each unknown entity will appear on its own line.
    """
    if len(unknown_entities) > 0:
        for entity in unknown_entities:
            problems.append(
                "Potential wrong name: '{}'".format(entity)
            )
    return


def rule_no_profanity(completion: str, problems: list):
    """ Rule: No Profanity

    No profanity allowed in the completion.
    """
    with open(profanity_csv_path, newline='') as f:
        reader = csv.reader(f)
        profanity = set([row[0] for row in reader])
    
    detected_profanities = []
    for word in completion.split():
        if word in profanity:
            detected_profanities.append("\'"+word+"\'")

    if len(detected_profanities) > 0:
        problem_string = ", ".join(detected_profanities)
        problems.append("Contains profanity: {}".format(problem_string))
    
    return


def rule_no_url(completion: str, problems: list):
    """ Rule: No URL

    No URL's allowed in the completion.
    """
    if "www." in completion:
        problems.append("Contains a URL.")
        
    return
