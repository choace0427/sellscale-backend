import requests
import json

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
