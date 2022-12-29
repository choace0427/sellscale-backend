import requests
import json
import os

from src.ml.models import GNLPModel, GNLPModelType, ModelProvider
from model_import import ClientArchetype
from app import db
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

BASELINE_GENERATION_MODELS = {
    GNLPModelType.OUTREACH: "davinci:ft-personal-2022-07-23-19-55-19",
    GNLPModelType.EMAIL_FIRST_LINE: "davinci:ft-personal-2022-12-04-05-14-26",
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


def create_baseline_model(archetype_id: int, model_type: GNLPModelType):
    ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
    archetype = ca.archetype

    model: GNLPModel = GNLPModel(
        model_provider=ModelProvider.OPENAI_GPT3,
        model_type=model_type,
        model_description="baseline_model_{}".format(archetype),
        model_uuid=BASELINE_GENERATION_MODELS[model_type],
        archetype_id=archetype_id,
    )
    db.session.add(model)
    db.session.commit()
    return model


def get_latest_custom_model(archetype_id: int, model_type: GNLPModelType):
    m: GNLPModel = (
        GNLPModel.query.filter(GNLPModel.archetype_id == archetype_id)
        .filter(GNLPModel.model_type == model_type)
        .order_by(GNLPModel.created_at.desc())
        .first()
    )

    if not m:
        m = create_baseline_model(archetype_id, model_type)

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


def get_personalized_first_line_for_client(
    archetype_id: int, model_type: GNLPModelType, prompt: str
):
    model_uuid, model_id = get_latest_custom_model(
        archetype_id=archetype_id, model_type=model_type
    )
    few_shot_prompt = "data: name: Tennessee Nunez<>industry: Internet<>company: TripActions<>title: Senior Growth Marketing Manager at TripActions<>notes: - TripActions is a travel, corporate card, and expense solution for businesses and employees \\n- TripActions builds more than just travel solutions -- <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: Great to connect with a fellow growth marketer! I hear TripActions is doing some amazing things with travel & corporate cards for employees. I know you all are building way more than travel solutions - excited to see where the product roadmap is headed.\n\n--\n\ndata: name: Richard Blatcher<>industry: Computer Software<>company: PROS<>title: Senior Director, Growth Marketing at PROS<>notes: - PROS is a leading provider of profit optimization software for enterprise clients ranging from tech companies to financial institutions \\n- Leads international growth marketing at PROS \\n- PROS is a computer software company with a focus on revenue management and digital transformation <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: I checked out PROS and love how you all have such a diverse set of enterprise clients, ranging from tech companies to financial institutions. The website says you are proven to pay out in less than 1 year - incredible!\n\n-- \n\ndata: name: Victoria Forcher<>industry: Marketing & Advertising<>company: Olist México<>title: Head of Marketing & Growth @ Olist | Ex Google | Ex Intuit | Co-Founder of Origen Digital<>notes: - Olist builds the infrastructure Retailers use to power their online sales through solving their digital needs 4 trillion x <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: Olist looks like an incredible infrastructure platform for online retailers! Seems like many global users use your platform to power their online sales. It's clear that your time as the Head of Marketing & Growth contributed significantly to all the success.\n\n-- \n\ndata: name: Laura Knipe<>industry: Information Technology & Services<>company: DigitalOcean<>title: Growth Marketing Analytics at DigitalOcean | NYU MBA Candidate<>notes: - DigitalOcean is an internet that helps developers, startups, and SMBs build and scale via the cloud \\n- DigitalOcean is building the future of technology infrastructure with open source solutions to accelerate application building <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: Kudos on all your success at DigitalOcean! Heading Marketing Analytics at such a fast-growing company must be quite a challenge. Your tools are clearly loved by developers, startups, and SMBs around the world - y'all are building the future of technology!\n\n--\n\ndata: name: Alyssa Musto<>industry: Sports<>company: National Hockey League (NHL)<>title: Director, Growth Marketing at National Hockey League (NHL)<>notes: - The National Hockey League governs professional hockey with a mission to: foster leadership and the values, dedication, integrity and passion to strengthen the beauty and euphoria around our sport <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: The thing I love most about The National Hockey League is how they foster leadership, dedication, integrity, and passion. I'm sure a lot of people appreciate the euphoria we get by watching and playing hockey!\n\n--\n\ndata: {prompt}\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage:".format(
        prompt=prompt
    )

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=few_shot_prompt,
        temperature=0.7,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    choices = response.get("choices", [])

    completion = choices[0].get("text", "")
    return (completion, model_id, few_shot_prompt)


def get_completion(bullet_model_id: str, prompt: str, max_tokens: int = 40, n: int = 1):
    model = BULLET_MODELS[bullet_model_id]
    return get_open_ai_completion(
        model=model, prompt=prompt, max_tokens=max_tokens, n=n
    )
