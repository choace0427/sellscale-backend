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
    archetype = ClientArchetype.query.get(archetype_id)
    if archetype.client_id == 9:  # adquick prompt
        few_shot_prompt = "prompt: name: Matthew Gryll<>industry: CRM<>company: Salesforce<>title: CMO<>notes: -The Motley Fool's article highlights Salesforce's impressive growth over its 24-year life span, providing a positive example of the impact growth and marketing can bring. -3 years as Director of Marketing at Salesforce.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. \n\ncompletion: I just read the article in Motley Fool about Salesforce's growth over it's 24-year lifespan. I can't beleive it's been that long! As Director of Growth marketing (congrats on almost 3 years!) there, seems like you and the team are constantly experimenting with new marketing strategies to grow.\n\n----\n\nprompt: name: Patrick Kerns<>industry: Education Technology<>company: Codecademy<>title: CMO<>notes: -Business Wire's article highlights Codecademy's impressive growth and marketing strategies that have enabled them to sustain double-digit revenue growth in their financial market conditions, geopolitical events, and changing climate. -2 years as Head of Brand and Integrated Marketing at Codecademy.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. \n\ncompletion: I just read an article on Business Insider about Codecademy's double-digit growth. This must have been a very busy 2 years now for you ha! As the Head of Brand and Int. Marketing, do you oversee how the company uses new marketing strategies to grow?\n\n----\n\nprompt: name: Harry Tulip<>industry: Entertainment <>company: DAZN<>title: CMO<>notes: -SportsPro Media's article highlights DAZN's acquisition of ELEVEN SPORTS and their international growth strategy, suggesting that they are a new player in the market and a potential threat to other sports broadcasters. -6 months as VP Brand Marketing at DAZN. -4 years as Head of Campaign Planning. -1 year as Senior Content Marketing Manager.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. \n\ncompletion: I read about DAZN's acquisition of ELEVN SPORTS as part of its growth strategy as an international player :) I'm excited to watch DAZN capture the market all over the world -  By any chance, are you  involved in expansion as VP Brand Marketing?\n\n----\n\nprompt: name: Matthew Jordan<>industry: Software<>company: GitLab<>title: CMO<>notes: -Yahoo Finance's article highlights the impressive resilience of GitLab's growth amid a challenging market, and the DevSecOps growth opportunity that GitLab has identified. -2 months as Senior Brand Manager at GitLab.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. \n\ncompletion: I just saw Yahoo Finance's article about GitLab's continued growth and opportunity in DevSecOps :) I see you just started with Gitlab - by any chance will you be heading up any growth initiatives in this area?\n\n----\n\nprompt: name: Bill Zrike<>industry: Beverages<>company: Constellation Brands<>title: CMO<>notes: -Constellation Brands is expected to post a growth in sales for its fiscal third quarter, with the company's sales growth being attributed to its beer and wine portfolio. -1 year as Sr. Manager of Emerging brands.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. \n\ncompletion: Constellation Brands is expanding its beer and wine portfolio!! Amazing.  I just read the MarketWatch article :) I see you maybe manage emerging brands? I'd love to learn more about how you approach growth strategies to capture these new markets.\n\n----\n\nprompt: name: David Goldberg <>industry: Software Development<>company: FormAssembly<>title: CMO<>notes: -Digital Journal's article highlights the growth of the lead generation software market, and provides a positive example of the growth that FormAssembly has experienced in the market. -5 months as Director of Growth Marketing at FormAssembly.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. \n\ncompletion: Pleasure to e-meet you - i wanted to reach out as I noticed you joined FA fairly recently to head up growth :)  There is so much potential in the lead generation software market, I just read a recent article about Formassembly in Digital Journal!\n\n----\n\nprompt: {prompt}\n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. \n\ncompletion:".format(
            prompt=prompt
        )
    else:
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
    return (completion, few_shot_prompt)


def get_completion(bullet_model_id: str, prompt: str, max_tokens: int = 40, n: int = 1):
    model = BULLET_MODELS[bullet_model_id]
    return get_open_ai_completion(
        model=model, prompt=prompt, max_tokens=max_tokens, n=n
    )
