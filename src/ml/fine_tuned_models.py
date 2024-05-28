import requests
import json
import yaml
import os

from src.ml.services import get_text_generation

from model_import import ClientArchetype, StackRankedMessageGenerationConfiguration
from app import db
from src.ml.openai_wrappers import (
    wrapped_chat_gpt_completion,
    wrapped_create_completion,
    OPENAI_COMPLETION_DAVINCI_3_MODEL,
    OPENAI_CHAT_GPT_4_MODEL,
)
from typing import Optional
import openai

OPENAI_KEY = os.environ.get("OPENAI_KEY")
openai.api_key = OPENAI_KEY


BULLET_MODELS = {
    "recent_job_summary": "davinci:ft-personal-2022-08-16-06-51-55",  # summarize recent job
    "recent_job_specialties": "davinci:ft-personal-2022-08-16-17-33-38",  # get recent company's specialties
    "current_experience_description": "davinci:ft-personal-2022-08-16-21-34-34",  # summarize experience
    "recent_recommendation": "davinci:ft-personal-2022-08-17-01-44-59",  # summarize recommendations
    "baseline_generation": "davinci:ft-personal-2022-07-23-19-55-19",  # baseline generation model
    "recent_recommendation_2": "davinci:ft-personal-2022-10-27-06-51-55",
}


def get_basic_openai_completion(prompt, max_tokens: int = 100, n: int = 1):
    OPENAI_URL = "https://api.openai.com/v1/completions"

    payload = json.dumps(
        {
            "model": "text-davinci-003",
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
    response = yaml.safe_load(raw_response)
    return [
        response["choices"][i]["text"].strip() for i in range(len(response["choices"]))
    ]


def get_few_shot_baseline_prompt(prompt: str):
    """
    New baseline prompt for LI generations.
    """
    few_shot_prompt = "prompt: name: Zalan Lima<>industry: Information Technology & Services<>company: QuintoAndar<>title: Analytics Manager II<>notes: - Read the recommendation Felipe left for you -- looks like you have an in-depth expertise of data modeling and connecting the dots when it comes to vast data pools \n-Saw that they've worked at ZServices, Digio, Intuit in the past\n-I'm building a product that leverages AI to speed up data science and I'd love to chat and see if we can work together!<>response: \n\ninstruction: Write a short two-liner personalized and complimentary introduction message that transitions well together.\n\ncompletion:  Hey Zalan! Felipe left you a fantastic rec -- it looks like you are a expert in data modeling when it comes to vast data pools. Considering your experiences, I'd love to share more about a tool I'm building that leverages AI to speed up data science. I'd love to chat and see if we can work together!\n\n--\n\nprompt: name: Dr. Debra Green Oliphant, DHA, MPA, FACHE, FMSP, CPMSM, CPCS<>industry: Hospital & Health Care<>company: Stanford Health Care<>title: Health Care Leader | Strategist | Change Agent | US Navy Veteran |<>notes: - Stanford Health Care is a hospital and healthcare company which heal humanity together n-Saw that they've worked at DRGO Consulting, LLC, US Navy Reserve, UCSF Medical Center in the pastn-Given the tight provider market, and our unique access to physicians, would you like to connect?<>response: \n\ninstruction: Write a short two-liner personalized and complimentary introduction message that transitions well together.\n\ncompletion: Hi Dr. Oliphant! I saw your profile and noticed that you've time at various leading health groups like UCSF and the US Navy - impressive! As you're a health care leader, and given the tight provider market, I'd love to connect and see if our unique access to physicians could help you at Stanford!\n\n--\n\nprompt: name: John Ehinger<>industry: Law Practice<>company: Westwood Holdings Group, Inc.<>title: Vice President and Associate General Counsel at Westwood Holdings Group, Inc.<>notes: -Spent 7 years at Westwood Holdings Group, Inc.\\n- Westwood Holdings Group, Inc. is a private investment management boutique and multi-asset solutions firm to investors \\n-Would love to talk about how Ramp can help add 3-4% to your bottom line and close your books 8x faster.<>response: \n\ninstruction: Write a short two-liner personalized and complimentary introduction message that transitions well together.\n\ncompletion:  Hey John! 7+ years at Westwood Holdings? That's incredible! Seeing that you're VP and associate general counsel, I imagine finances are a priority for you and the team. I'd love to chat about how Ramp can help add 3-4% to your bottom line and help you close your books 8x faster.  \n\n--\n\nprompt: name: Mindy Schneider, CPRP<>industry: Hospital & Health Care<>company: Valley Medical Center<>title: Provider/Physician Recruiter at Valley Medical Center<>notes: -Congrats on your recent 1 year anniversary at Valley Medical Center. Congratulations!\\n-Saw that you've worked at Premera Blue Cross, Colorado State University, Poudre School District in the past\\n-I wanted to get your thoughts on a physician placement solution I’m building - open to chat?<>response: \n\ninstruction: Write a short two-liner personalized and complimentary introduction message that transitions well together.\n\ncompletion:  Hi Mindy! Congrats on your recent 1 year anniversary at Valley Medical Center! Considering your vast experiences at Colorado State, Poudre School, and Premera Blue Cross, I wanted to get your thoughts on a physician placement solution I'm building - open to chat? \n\n--\n\nprompt: {prompt}\n\ninstruction: Write a short two-liner personalized and complimentary introduction message that transitions well together.\n\ncompletion:".format(
        prompt=prompt
    )
    completions = get_basic_openai_completion(few_shot_prompt, n=1)
    return completions


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


def get_config_completion(
    config: Optional[StackRankedMessageGenerationConfiguration],
    prompt: str,
):
    if not config:
        raise ValueError("No config provided")
    few_shot_prompt: str = config.computed_prompt.format(prompt=prompt)

    response = get_text_generation(
        [
            {"role": "system", "content": few_shot_prompt},
        ],
        temperature=0.65,
        max_tokens=240,
        model=OPENAI_CHAT_GPT_4_MODEL,
        type="VOICE_MSG",
    )
    return (response, few_shot_prompt)


def get_computed_prompt_completion(
    computed_prompt: str,
    prompt: str,
):
    few_shot_prompt: str = computed_prompt.format(prompt=prompt)
    response = get_text_generation(
        [
            {"role": "system", "content": few_shot_prompt},
        ],
        temperature=0.65,
        max_tokens=100,
        model=OPENAI_CHAT_GPT_4_MODEL,
        type="VOICE_MSG",
    )
    return (response, few_shot_prompt)


def get_completion(bullet_model_id: str, prompt: str, max_tokens: int = 40, n: int = 1):
    model = BULLET_MODELS[bullet_model_id]
    return get_open_ai_completion(
        model=model, prompt=prompt, max_tokens=max_tokens, n=n
    )
