import requests
import json
import yaml
import os

from src.ml.services import get_text_generation

from src.ml.models import GNLPModel, GNLPModelType, ModelProvider
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


# DEPRECATE
# def create_baseline_model(archetype_id: int, model_type: GNLPModelType):
#     ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
#     archetype = ca.archetype

#     model: GNLPModel = GNLPModel(
#         model_provider=ModelProvider.OPENAI_GPT3,
#         model_type=model_type,
#         model_description="baseline_model_{}".format(archetype),
#         model_uuid=BASELINE_GENERATION_MODELS[model_type],
#         archetype_id=archetype_id,
#     )
#     db.session.add(model)
#     db.session.commit()
#     return model


# def get_latest_custom_model(archetype_id: int, model_type: GNLPModelType):
#     m: GNLPModel = (
#         GNLPModel.query.filter(GNLPModel.archetype_id == archetype_id)
#         .filter(GNLPModel.model_type == model_type)
#         .order_by(GNLPModel.created_at.desc())
#         .first()
#     )

#     if not m:
#         m = create_baseline_model(archetype_id, model_type)

#     return m.model_uuid, m.id


# def get_custom_completion_for_client(
#     archetype_id: int,
#     model_type: GNLPModelType,
#     prompt: str,
#     max_tokens: int = 40,
#     n: int = 1,
# ):
#     model_uuid, model_id = get_latest_custom_model(
#         archetype_id=archetype_id, model_type=model_type
#     )

#     return (
#         get_open_ai_completion(
#             model=model_uuid, prompt=prompt, max_tokens=max_tokens, n=n
#         ),
#         model_id,
#     )


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


def get_personalized_first_line_for_client(
    archetype_id: int, model_type: GNLPModelType, prompt: str
):
    archetype = ClientArchetype.query.get(archetype_id)
    if archetype.client_id == 9:  # adquick prompt
        # SERP + YOE Prompt
        few_shot_prompt = "prompt: name: Matthew Gryll<>industry: CRM<>company: Salesforce<>title: CMO<>notes: -The Motley Fool's article highlights Salesforce's impressive growth over its 24-year life span, providing a positive example of the impact growth and marketing can bring. -3 years as Director of Marketing at Salesforce.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I just read the article in Motley Fool about Salesforce's growth over it's 24-year lifespan. I can't beleive it's been that long! As a director of growth marketing (congrats on almost 3 years!) there, seems like you and the team are constantly experimenting with new marketing strategies to grow.\n\n----\n\nprompt: name: Patrick Kerns<>industry: Education Technology<>company: Codecademy<>title: CMO<>notes: -Business Wire's article highlights Codecademy's impressive growth and marketing strategies that have enabled them to sustain double-digit revenue growth in their financial market conditions, geopolitical events, and changing climate. -2 years as Head of Brand and Integrated Marketing at Codecademy.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I just read an article on Business Insider about Codecademy's double-digit growth. This must have been a very busy 2 years now for you! As the head of brand and marketing, I imagine that you probably oversee how the company uses new marketing strategies to grow.\n\n----\n\nprompt: name: Harry Tulip<>industry: Entertainment <>company: DAZN<>title: CMO<>notes: -SportsPro Media's article highlights DAZN's acquisition of ELEVEN SPORTS and their international growth strategy, suggesting that they are a new player in the market and a potential threat to other sports broadcasters. -6 months as VP Brand Marketing at DAZN. -4 years as Head of Campaign Planning. -1 year as Senior Content Marketing Manager.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: Wow, 7 years at DAZN and still growing! I just read the Yahoo Finance feature on the SVOD European Market - seems like you guys are doing something right!\n\n----\n\nprompt: name: Matthew Jordan<>industry: Software<>company: GitLab<>title: CMO<>notes: -Yahoo Finance's article highlights the impressive resilience of GitLab's growth amid a challenging market, and the DevSecOps growth opportunity that GitLab has identified. -2 months as Senior Brand Manager at GitLab.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I just saw Yahoo Finance's article about GitLab's continued growth and opportunity in DevSecOps :) I see you just started with Gitlab. Must be exciting to be heading up growth & brand initiatives for such a rapidly expanding company.\n\n----\n\nprompt: name: Bill Zrike<>industry: Beverages<>company: Constellation Brands<>title: CMO<>notes: -Constellation Brands is expected to post a growth in sales for its fiscal third quarter, with the company's sales growth being attributed to its beer and wine portfolio. -1 year as Sr. Manager of Emerging brands.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: Constellation Brands is expanding its beer and wine portfolio!! Amazing. I just read the MarketWatch article :) I'd love to learn more about how you approach growth strategies to capture these new markets.\n\n----\n\nprompt: name: David Goldberg <>industry: Software Development<>company: FormAssembly<>title: CMO<>notes: -Digital Journal's article highlights the growth of the lead generation software market, and provides a positive example of the growth that FormAssembly has experienced in the market. -5 months as Director of Growth Marketing at FormAssembly.<>tags: growth, marketing<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: Pleasure to e-meet you - i wanted to reach out as I noticed you joined FA fairly recently to head up growth :)  There is so much potential in the lead generation software market, I just read a recent article about Formassembly in Digital Journal!\n\n----\n\nprompt: name: Laura Knipe<>industry: Information Technology & Services<>company: DigitalOcean<>title: Growth Marketing Analytics at DigitalOcean | NYU MBA Candidate<>notes: -Just a few weeks ago I read the article from Yahoo Finance about Needham's bullishness on DigitalOcean. DigitalOcean's growth has been impressive and seems that the company has a lot of room left for growth.<>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I just saw the Yahoo Finance article about DigitalOcean's impressive growth and Needham's bullishness. There must be a lot talent on your growth team!\n\n----\n\nprompt: {{prompt}}\n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion:".format(
            prompt=prompt
        )

        # Linkedin Transformer Prompt
        # few_shot_prompt = "prompt: name: Alex Quaresma<>industry: Retail<>company: Endy<>title: Brand Growth & Customer Marketing at Endy<>notes: -I came across your website and saw the favorable reviews on Endy Love products, with customers giving it a 5 star rating.\n- Endy is revolutionizing the way people sleep by selling mattresses online \n- Endy is a direct to consumer furniture company with a focus on sleep and customer service <>response: \n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I came across your website and saw the favorable reviews on Endy products, with customers giving it a 5 star rating. It looks like Endy is winning - you guys are doing an awesome job!\n\n----\n\nprompt: name: Katerina Clark<>industry: Marketing & Advertising<>company: Fetch by The Dodo<>title: Director Growth Marketing at Fetch by The Dodo<>notes: -Saw you've worked at iQuanti,, Mindshare, Reprise Media, IPG Mediabrands\n- Fetch by The Dodo is the only pet insurance provider recommended by the #1 animal brand in the world \n-14+ years of experience in industry<>response:\n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I've been following you since I read your case study on iQuanti - really cool to see the breadth of experiences you've had over the years with different brands and media companies. Fascinating.\n\n----\n\nprompt: name: Avantika Saxena<>industry: Information Technology & Services<>company: Fresh Prep<>title: Director, Growth Marketing<>notes: - Leads growth marketing at Fresh Prep \n- @FreshPrep is changing #Edibles as we know it -- description: Fresh Prep is changing Edibles as we know it with Canada’s most sustainable #MealKit delivery service \n-Saw you've worked at Best Buy Canada, eBay, T-Mobile<>response:\n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I'm impressed by the impact you've had at Fresh Prep - being Canada's most sustainable MealKit delivery service is no easy feat 👍\n\n----\n\nprompt: name: Greg Adams<>industry: Marketing & Advertising<>company: Chameleon Collective<>title: Partner • Growth Marketing and eCommerce Consultant • Interim Leader • Marketing Strategy • Digital Transformation<>notes: - Chameleon Collective is a management consulting firm that helps with executive recruiting, advertising, B2B, retail, B2C, and growth marketing \n-Saw that you have experiences at Kelsen Products, 7 For All Mankind, BCBGMAXAZRIAGROUP\n- Leads marketing at Chameleon Collective and on the Leadership Council, builds growth through customers <>response:\n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion: I'm really impressed by the marketing strategies that you've spearheaded at Chameleon Collective. I'm curious to learn more about the executive recruiting facet of the business. How do you leverage the success of your team to accomplish that?\n\n----\n\nprompt: {prompt}\n\ninstruction: Write a two-liner about the recent company news. Include references to the tags and their experience at the company. Tie in with growth.\n\ncompletion:".format(
        #     prompt=prompt
        # )

    else:
        few_shot_prompt = "data: name: Tennessee Nunez<>industry: Internet<>company: TripActions<>title: Senior Growth Marketing Manager at TripActions<>notes: - TripActions is a travel, corporate card, and expense solution for businesses and employees \\n- TripActions builds more than just travel solutions -- <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: Great to connect with a fellow growth marketer! I hear TripActions is doing some amazing things with travel & corporate cards for employees. I know you all are building way more than travel solutions - excited to see where the product roadmap is headed.\n\n--\n\ndata: name: Richard Blatcher<>industry: Computer Software<>company: PROS<>title: Senior Director, Growth Marketing at PROS<>notes: - PROS is a leading provider of profit optimization software for enterprise clients ranging from tech companies to financial institutions \\n- Leads international growth marketing at PROS \\n- PROS is a computer software company with a focus on revenue management and digital transformation <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: I checked out PROS and love how you all have such a diverse set of enterprise clients, ranging from tech companies to financial institutions. The website says you are proven to pay out in less than 1 year - incredible!\n\n-- \n\ndata: name: Victoria Forcher<>industry: Marketing & Advertising<>company: Olist México<>title: Head of Marketing & Growth @ Olist | Ex Google | Ex Intuit | Co-Founder of Origen Digital<>notes: - Olist builds the infrastructure Retailers use to power their online sales through solving their digital needs 4 trillion x <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: Olist looks like an incredible infrastructure platform for online retailers! Seems like many global users use your platform to power their online sales. It's clear that your time as the Head of Marketing & Growth contributed significantly to all the success.\n\n-- \n\ndata: name: Laura Knipe<>industry: Information Technology & Services<>company: DigitalOcean<>title: Growth Marketing Analytics at DigitalOcean | NYU MBA Candidate<>notes: - DigitalOcean is an internet that helps developers, startups, and SMBs build and scale via the cloud \\n- DigitalOcean is building the future of technology infrastructure with open source solutions to accelerate application building <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: Kudos on all your success at DigitalOcean! Heading Marketing Analytics at such a fast-growing company must be quite a challenge. Your tools are clearly loved by developers, startups, and SMBs around the world - y'all are building the future of technology!\n\n--\n\ndata: name: Alyssa Musto<>industry: Sports<>company: National Hockey League (NHL)<>title: Director, Growth Marketing at National Hockey League (NHL)<>notes: - The National Hockey League governs professional hockey with a mission to: foster leadership and the values, dedication, integrity and passion to strengthen the beauty and euphoria around our sport <>response:\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage: The thing I love most about The National Hockey League is how they foster leadership, dedication, integrity, and passion. I'm sure a lot of people appreciate the euphoria we get by watching and playing hockey!\n\n--\n\ndata: {prompt}\n\ninstruction: Write a personalized first sentence of an email sequence without their first name.\n\nmessage:".format(
            prompt=prompt
        )

    text = wrapped_chat_gpt_completion(
        messages=[
            {"role": "user", "content": few_shot_prompt},
        ],
        temperature=0.65,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )

    return (text, few_shot_prompt)


def get_completion(bullet_model_id: str, prompt: str, max_tokens: int = 40, n: int = 1):
    model = BULLET_MODELS[bullet_model_id]
    return get_open_ai_completion(
        model=model, prompt=prompt, max_tokens=max_tokens, n=n
    )
