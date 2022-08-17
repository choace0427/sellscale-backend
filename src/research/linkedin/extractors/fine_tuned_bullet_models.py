import requests
import json
import os

OPENAI_KEY = os.environ.get('OPENAI_KEY')


BULLET_MODELS = {
    "recent_job_summary": "davinci:ft-personal-2022-08-16-06-51-55",
    "recent_job_specialties": "davinci:ft-personal-2022-08-16-17-33-38",
    "current_experience_description": "davinci:ft-personal-2022-08-16-21-34-34",
    "recent_recommendation": "davinci:ft-personal-2022-08-17-01-44-59"
}

def get_completion(bullet_model_id: str, prompt: str):
    model = BULLET_MODELS[bullet_model_id]

    url = "https://api.openai.com/v1/completions"

    payload=json.dumps({
        "prompt": prompt,
        "model": model,
        "n": 1,
        "stop": "XXX",
        "max_tokens": 40
    })
    headers = {
        'Authorization': 'Bearer {}'.format(OPENAI_KEY),
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    response_json = response.json()
    completion = response_json.get('choices', [])[0].get('text', '')
    return completion
