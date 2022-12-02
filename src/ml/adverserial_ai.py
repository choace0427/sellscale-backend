import requests
import json
from model_import import GeneratedMessage
from app import db

# View experiment here: https://www.notion.so/sellscale/Adversarial-AI-v0-Experiment-901a97de91a845d5a83063f3d6606a4a
ADVERSARIAL_MODEL = "curie:ft-personal-2022-10-27-20-07-22"


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


def adversarial_ai_ruleset(message_id: int):
    """Adversarial AI ruleset.

    Args:
        message_id (int): The message ID to run the ruleset against.

    Returns:
        bool: Whether the message passes the ruleset.
    """
    from src.message_generation.services import (
        generated_message_has_entities_not_in_prompt,
    )

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    prompt = message.prompt
    completion = message.completion

    if message.unknown_named_entities == None:
        generated_message_has_entities_not_in_prompt(message_id)

    problems = []
    if len(message.unknown_named_entities) > 0:
        problems.append(
            "Unknown named entities: {}".format(
                '", "'.join(message.unknown_named_entities)
            )
        )

    if "i have" in completion.lower():
        problems.append("Uses first person 'I have'.")

    if "www." in completion.lower():
        problems.append("Contains a URL.")

    if " me " in completion.lower():
        problems.append("Contains 'me'.")

    if "MD" in prompt and "Dr" not in completion:
        problems.append("Contains 'MD' but not 'Dr'. in title")

    if "they've worked" in completion.lower():
        problems.append("Contains 'they've worked'.")

    if "i've spent" in completion.lower():
        problems.append("Contains 'i've spent'.")

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.problems = problems
    db.session.add(message)
    db.session.commit()

    return problems
