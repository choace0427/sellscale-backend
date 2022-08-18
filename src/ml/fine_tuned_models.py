import requests
import json
import os

OPENAI_KEY = os.environ.get('OPENAI_KEY')


BULLET_MODELS = {
    "recent_job_summary": "davinci:ft-personal-2022-08-16-06-51-55", # summarize recent job
    "recent_job_specialties": "davinci:ft-personal-2022-08-16-17-33-38", # get recent company's specialties
    "current_experience_description": "davinci:ft-personal-2022-08-16-21-34-34", # summarize experience
    "recent_recommendation": "davinci:ft-personal-2022-08-17-01-44-59", # summarize recommendations
    'baseline_generation': 'davinci:ft-personal-2022-07-23-19-55-19', # baseline generation model
}

def get_completion(bullet_model_id: str, prompt: str, max_tokens: int = 40, n: int = 1):
    model = BULLET_MODELS[bullet_model_id]

    url = "https://api.openai.com/v1/completions"

    payload=json.dumps({
        "prompt": prompt,
        "model": model,
        "n": n,
        "stop": "XXX",
        "max_tokens": max_tokens
    })
    headers = {
        'Authorization': 'Bearer {}'.format(OPENAI_KEY),
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    response_json = response.json()
    choices = response_json.get('choices', [])

    if (n == 1):
        completion = choices[0].get('text', '')
        return completion

    else:
        return [choices[x].get('text', '') for x in range(len(choices))]