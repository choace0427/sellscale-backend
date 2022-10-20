import requests
import json
import os

from src.ml.models import GNLPModel, GNLPModelType

OPENAI_KEY = os.environ.get("OPENAI_KEY")


BULLET_MODELS = {
    "recent_job_summary": "davinci:ft-personal-2022-08-16-06-51-55",  # summarize recent job
    "recent_job_specialties": "davinci:ft-personal-2022-08-16-17-33-38",  # get recent company's specialties
    "current_experience_description": "davinci:ft-personal-2022-08-16-21-34-34",  # summarize experience
    "recent_recommendation": "davinci:ft-personal-2022-08-17-01-44-59",  # summarize recommendations
    "baseline_generation": "davinci:ft-personal-2022-07-23-19-55-19",  # baseline generation model
}


def get_basic_openai_completion(prompt, max_tokens: int = 100, n: int = 1):
    OPENAI_URL = "https://api.openai.com/v1/completions"

    payload = json.dumps(
        {
            "model": "text-davinci-002",
            "prompt": prompt,
            "n": n,
            "stop": "XXX",
            "max_tokens": max_tokens,
        }
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}".format(OPENAI_KEY),
    }

    raw_response = requests.request(
        "POST", OPENAI_URL, headers=headers, data=payload
    ).text
    response = json.loads(raw_response)
    return [
        response["choices"][i]["text"].strip() for i in range(len(response["choices"]))
    ]


def get_open_ai_completion(model: str, prompt: str, max_tokens: int = 40, n: int = 1):
    url = "https://api.openai.com/v1/completions"

    payload = json.dumps(
        {
            "prompt": prompt,
            "model": model,
            "n": n,
            "stop": "XXX",
            "max_tokens": max_tokens,
        }
    )
    headers = {
        "Authorization": "Bearer {}".format(OPENAI_KEY),
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    response_json = response.json()
    choices = response_json.get("choices", [])

    if n == 1:
        completion = choices[0].get("text", "")
        return completion

    else:
        return [choices[x].get("text", "") for x in range(len(choices))]


def get_latest_custom_model(archetype_id: int, model_type: GNLPModelType):
    m: GNLPModel = (
        GNLPModel.query.filter(GNLPModel.archetype_id == archetype_id)
        .filter(GNLPModel.model_type == model_type)
        .order_by(GNLPModel.created_at.desc())
        .first()
    )

    if not m:
        raise Exception("Model not found.")

    return m.model_uuid, m.id


def get_custom_completion_for_client(
    archetype_id: int,
    model_type: GNLPModelType,
    prompt: str,
    max_tokens: int = 40,
    n: int = 1,
):
    model_uuid, model_id = get_latest_custom_model(
        archetype_id=archetype_id, model_type=model_type
    )

    return (
        get_open_ai_completion(
            model=model_uuid, prompt=prompt, max_tokens=max_tokens, n=n
        ),
        model_id,
    )


def get_completion(bullet_model_id: str, prompt: str, max_tokens: int = 40, n: int = 1):
    model = BULLET_MODELS[bullet_model_id]
    return get_open_ai_completion(
        model=model, prompt=prompt, max_tokens=max_tokens, n=n
    )
