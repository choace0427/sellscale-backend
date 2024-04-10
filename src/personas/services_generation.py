import random
from src.client.models import (
    ClientArchetype,
    ClientAssetType,
    ClientAssets,
    ClientSDR,
    Client,
    DemoFeedback,
)
from model_import import Individual
from src.client.archetype.services_client_archetype import get_archetype_assets
from src.ml.services import get_text_generation
import re
from src.utils.string.string_utils import rank_number

GEN_AMOUNT = 5
ASSET_AMOUNT = 2

MESSAGE_MODEL = "gpt-4"  # "claude-3-opus-20240229"
CLEANING_MODEL = "gpt-4-turbo-preview"


def get_sdr_prompting_context_info(client_sdr_id: int):

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(sdr.client_id)
    individual: Individual = Individual.query.get(sdr.individual_id)

    sdr_name = f"""Your Name: {sdr.name}"""
    sdr_email = (
        f"""Your Email: {individual.email}""" if individual and individual.email else ""
    )
    sdr_phone = (
        f"""Your Phone #: {individual.phone}"""
        if individual and individual.phone
        else ""
    )
    sdr_title = (
        f"""Your Title: {individual.title}""" if individual and individual.title else ""
    )
    sdr_bio = f"""Your Bio: {individual.bio}""" if individual and individual.bio else ""
    sdr_job_description = (
        f"""Your Job Description: {individual.recent_job_description}"""
        if individual and individual.recent_job_description
        else ""
    )
    sdr_industry = (
        f"""Your Industry: {individual.industry}"""
        if individual and individual.industry
        else ""
    )
    sdr_location = (
        f"""Your Location: {individual.location.get("default")}"""
        if individual and individual.location and individual.location.get("default")
        else ""
    )
    sdr_school = (
        f"""Your School: {individual.recent_education_school}"""
        if individual and individual.recent_education_school
        else ""
    )
    sdr_degree = (
        f"""Your Degree: {individual.recent_education_degree}"""
        if individual and individual.recent_education_degree
        else ""
    )
    sdr_education_field = (
        f"""Your Education Field: {individual.recent_education_field}"""
        if individual and individual.recent_education_field
        else ""
    )
    sdr_education_start_date = (
        f"""Your Education Start Date: {individual.recent_education_start_date}"""
        if individual and individual.recent_education_start_date
        else ""
    )
    sdr_education_end_date = (
        f"""Your Education End Date: {individual.recent_education_end_date}"""
        if individual and individual.recent_education_end_date
        else ""
    )

    client_name = f"""Your Company Name: {client.company}""" if client.company else ""
    client_tagline = (
        f"""Your Company Tagline: {client.tagline}""" if client.tagline else ""
    )
    client_description = (
        f"""Your Company Description: {client.description}"""
        if client.description
        else ""
    )
    client_key_value_props = (
        f"""Your Company Key Value Props: {client.value_prop_key_points}"""
        if client.value_prop_key_points
        else ""
    )
    client_mission = (
        f"""Your Company Mission: {client.mission}""" if client.mission else ""
    )
    client_impressive_facts = (
        f"""Your Company Impressive Facts: {client.impressive_facts}"""
        if client.impressive_facts
        else ""
    )
    # sdr_work_history = (
    #     "Your Work History (most recent first): \n"
    #     + "\n".join(
    #         [
    #             f"History - Company Name: {work.get('company_name')}, Title: {work.get('title')}, Start Date: {work.get('start_Date', '?')}, End Date: {work.get('start_Date', '?')}"
    #             for work in parse_work_history(individual.work_history)
    #         ]
    #     )
    #     if individual and individual.work_history
    #     else ""
    # )

    # day, day_of_month, month, year = get_current_time_casual(sdr.timezone)

    context_info = f"""
Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    {sdr_name}
    {sdr_email}
    {sdr_phone}
    {sdr_title}
    {sdr_bio}
    {sdr_job_description}
    {sdr_industry}
    {sdr_location}
    {sdr_school}
    {sdr_degree}
    {sdr_education_field}
    {sdr_education_start_date}
    {sdr_education_end_date}
    {client_name}
    {client_tagline}
    {client_description}
    {client_key_value_props}
    {client_mission}
    {client_impressive_facts}
    """.strip()

    return context_info


def generate_sequence(
    client_id: int,
    archetype_id: int,
    sequence_type: str,
    step_num: int,
    additional_prompting: str,
):

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    context_info = get_sdr_prompting_context_info(archetype.client_sdr_id)

    raw_assets = get_archetype_assets(archetype_id)
    all_assets = [
        {
            "id": asset.get("id"),
            "title": asset.get("asset_key"),
            "value": asset.get("asset_value"),
            "tag": (
                asset.get("asset_tags", [])[0]
                if len(asset.get("asset_tags", [])) > 0
                else ""
            ),
        }
        for asset in raw_assets
    ]

    assets = random.sample(
        all_assets,
        min(ASSET_AMOUNT, len(all_assets)),
    )
    assets_str = "## Assets: \n" + "\n\n".join(
        [
            f"Title: {asset.get('title')}\nValue: {asset.get('value')}\nTag: {asset.get('tag')}\nID: {asset.get('id')}"
            for asset in assets
        ]
    )

    output = []
    if sequence_type == "EMAIL":
        if step_num == 1:
            output.append(
                {
                    "result": clean_output_with_ai(
                        generate_email_initial(
                            client_id=client_id,
                            archetype_id=archetype_id,
                            context_info=context_info,
                            assets_str=assets_str,
                            additional_prompting=additional_prompting,
                        )
                    ),
                    "assets": assets,
                    "step_num": step_num,
                }
            )
        else:

            output.append(
                {
                    "result": clean_output_with_ai(
                        clean_output(
                            generate_email_follow_up_quick_and_dirty(
                                client_id=client_id,
                                archetype_id=archetype_id,
                                step_num=step_num,
                                context_info=context_info,
                                assets_str=assets_str,
                                additional_prompting=additional_prompting,
                            )
                        )
                    ),
                    "assets": assets,
                    "step_num": step_num,
                }
            )

    else:
        if step_num == 1:
            if sequence_type == "LINKEDIN-CTA":
                output.append(
                    {
                        "result": clean_output_with_ai(
                            generate_linkedin_cta(
                                client_id=client_id,
                                archetype_id=archetype_id,
                                context_info=context_info,
                                assets_str=assets_str,
                                additional_prompting=additional_prompting,
                            )
                        ),
                        "assets": assets,
                        "step_num": step_num,
                    }
                )
            else:
                output.append(
                    {
                        "result": clean_output_with_ai(
                            generate_linkedin_initial(
                                client_id=client_id,
                                archetype_id=archetype_id,
                                context_info=context_info,
                                assets_str=assets_str,
                                additional_prompting=additional_prompting,
                            )
                        ),
                        "assets": assets,
                        "step_num": step_num,
                    }
                )
        else:

            output.append(
                {
                    "result": clean_output_with_ai(
                        clean_output(
                            generate_linkedin_follow_up(
                                client_id=client_id,
                                archetype_id=archetype_id,
                                step_num=step_num,
                                context_info=context_info,
                                assets_str=assets_str,
                                additional_prompting=additional_prompting,
                            )
                        )
                    ),
                    "assets": assets,
                    "step_num": step_num,
                }
            )

    return output


def generate_email_initial(
    client_id: int,
    archetype_id: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
):
    """

    You are working to create a cold email in a sequence for generative outreach to prospects.
    The email should use different assets that have a unique value prop, pain point, case study, unique facts, etc that can be used in to make that email stand out. It should also have a particular angle or approach to the outreach.
    When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.


    """

    prompt = f"""
    
You are an angle creator for outbound emails. Your goal is to return new, creative outbound angles and copy for generative outreach to prospects.
When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

I will give you 3 few shot examples. Each example contains

- ## Assets
- ## Output: Email
- ## Angle: Angle-based
- ## Angle Description: Description of the angle

I’m going to give you outreach information (which includes an asset), and you are to return {GEN_AMOUNT} angles and their associated email copy.

The more diverse the outputs are, and creative, the better. You should follow general email practices like keeping it short, concise, and free of fillers such as (”I hope this finds you well”).
Pick 1-3 assets to utilize in your email. In your output say the IDs of the assets you used. Be creative and use them in different ways.

{additional_prompting if additional_prompting else ""}

Here's some previous examples of what you're expected to generate.
# Previous Example 1 #
-------------------------------------------------------------

Please generate a cold email outline for generative outreach to prospects.

{get_email_example(1, 1)}

-------------------------------------------------------------

# Previous Example 2 #
-------------------------------------------------------------

Please generate a cold email outline for generative outreach to prospects.


{get_email_example(2, 1)}

-------------------------------------------------------------

# Previous Example 3 #
-------------------------------------------------------------

Please generate a cold email outline for generative outreach to prospects.

{get_email_example(3, 1)}

-------------------------------------------------------------

# Your Turn #
Okay now it's your turn to generate an email. Good luck! Remember to keep your email short and concise and stay off the spam folder!



Please generate a cold email outline for generative outreach to prospects.

{context_info}


{assets_str}


## General guidelines

- Final note - each email should follow a different structure. Here are some things you can vary on:
    - length: extremely short to medium
    - tone - informal, creative, informational (try different types but avoid being salesy)
    - structure - mix up email approach
- Keep the angles one word, then -based. Such as `Persona-based`

## Output:

    """.strip()

    #    print(prompt)

    print("GENERATING EMAIL INITIAL")
    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=MESSAGE_MODEL,
            max_tokens=4000,
            type="EMAIL",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    return completion


def generate_email_follow_up_quick_and_dirty(
    client_id: int,
    archetype_id: int,
    step_num: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
):

    prompt = f"""
    
    You're an angle creator for outbound emails. Your goal is to return new, creative outbound angles and copy for generative outreach to prospects.
    When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.
    
    You need to come up with a follow-up email for a generative outreach sequence. The prospect didn't respond to the initial cold email, so you need to come up with a follow-up email that will get their attention.
    
    
    I’m going to give you outreach information (which includes an asset), and you are to return {GEN_AMOUNT} angles and their associated email copy.

    The more diverse the outputs are, and creative, the better. You should follow general email practices like keeping it short, concise, and free of fillers such as (”I hope this finds you well”).


    {additional_prompting if additional_prompting else ""}
    
    
    Here's some assets, use them to create a follow-up email. Pick 1-3 assets to utilize in your email. But, again, be creative and use them in different ways. Say the IDs of the assets you used.
    
    {assets_str}
    
    
    {context_info}
    
    
    
    ## Some examples:
    
    ---------------------------------------------------
    ## Output:
    ### Message:
    Hello [prospect name],

    Hope your week is going well. It was great to hear about your [business pain point] on our last call. I think [company name] can help you [insert benefit].

    I'd love the opportunity to tell you a few of my ideas over a 15-minute call. Are you free this Thursday? If so, feel free to book some time on my calendar: [insert calendar link].

    Thanks,

    [Signature]
    ---------------------------------------------------
    ## Output:
    ### Message:
    Hello [prospect name],

    Just bumping this up in your inbox. Did you get a chance to speak to [higher-up] about moving forward with [product or service]?

    If not, I’d love to set up a phone call so I can get your team started [achieving X results]. Are you and your manager available on Wednesday morning for a brief phone call?

    Thanks,

    [Signature]
    ---------------------------------------------------
    ## Output:
    ### Message:
    Hey [prospect name],

    It seems like it’s not a great time for us to connect, but I really think [specific features] could help your business [achieve X results].

    If you’re not the right person to talk to, whom should I reach out to?

    Thanks,
    ---------------------------------------------------
    
    
    ## General guidelines

    - Final note - each email should follow a different structure. Here are some things you can vary on:
        - length: extremely short to medium
        - tone - informal, creative, informational (try different types but avoid being salesy)
        - structure - mix up email approach
    - Keep the angles one word, then -based. Such as `Persona-based`
    - Make sure emails (both words and tone) are short and concise

    ## Output:
    
    """.strip()

    print(f"GENERATING EMAIL FOLLOW UP {step_num}")
    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=MESSAGE_MODEL,
            max_tokens=4000,
            type="EMAIL",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    return completion


def generate_linkedin_initial(
    client_id: int,
    archetype_id: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
):

    prompt = f"""
  
You are an angle creator for outbound LinkedIn. Your goal is to return new, creative outbound angles and copy for generative outreach to prospects.
When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

{additional_prompting}

I will give you 3 few shot examples. Each example contains

- ## Assets
- ## Output: LinkedIn message
- ## Angle: Angle-based
- ## Angle Description: Description of the angle

I’m going to give you outreach information (which includes an asset), and you are to return 6 angles and their associated cold outreach LinkedIn message.

The more diverse the outputs are, and creative, the better. You should follow general LinkedIn message practices like keeping it short, concise, and free of fillers such as (”I hope this finds you well”).
Pick 1-3 assets to utilize in your message. In your output say the IDs of the assets you used. Be creative and use them in different ways.

Here's some previous examples of what you're expected to generate.
# Previous Example 1 #
-------------------------------------------------------------

Please generate a cold outbound LinkedIn message outline for generative outreach to prospects.


## Assets: 
Title: Better estimates
Value: We help create better estimates for stubs on bid day
Tag: Value Prop


## Output:
### Message:
Hey [[ prospect first name ]] – saw you do some [[ prospect industry work ]] work and wanted to reach out. We’re working on a new platform for faster and more organized estimates from subs on bid day. Would be great to share more and get your thoughts on it.
### Angle: Solution-based
### Angle Description: Helps them solve a problem related to their work


-------------------------------------------------------------
# Previous Example 2 #
-------------------------------------------------------------

Please generate a cold outbound LinkedIn message outline for generative outreach to prospects.


## Assets: 
Title: Diabetes Care
Value: Looks after of patients with Diabetes during Covid 19
Tag: Value Prop


## Output:
### Message:
[[ prospect first name ]], I work with Diabetes Educators who are on the frontlines caring for patients with Diabetes during Covid 19, and I was hoping to connect with you here!
### Angle: Value-based
### Angle Description: Speaks of the value they provide in general

-------------------------------------------------------------

# Your Turn #
Okay now it's your turn to generate some messages. Good luck!


Please generate a cold outbound LinkedIn message outline for generative outreach to prospects.


{context_info}


## General guidelines

- Final note - each message should follow a different structure. Here are some things you can vary on:
    - tone - informal, creative, informational (try different types but avoid being salesy)
    - structure - mix up message approach
- Keep the angles one word, then -based. Such as `Persona-based`
- remember, on LinkedIn, you can only include 300 characters in an initial outbound message. Please keep your messages under 3 sentences.



## Assets: 
{assets_str}


## Output:
""".strip()

    print(f"GENERATING LINKEDIN INITIAL")
    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=MESSAGE_MODEL,
            max_tokens=4000,
            type="EMAIL",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    return completion


def generate_linkedin_follow_up(
    client_id: int,
    archetype_id: int,
    step_num: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
):

    prompt = f"""
  
You are an angle creator for outbound LinkedIn. Your goal is to return new, creative outbound angles and copy for generative replies on generative outreach to prospects.
When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

{additional_prompting}

I will give you 3 few shot examples. Each example contains

- ## Assets
- ## Output: LinkedIn message
- ## Angle: Angle-based
- ## Angle Description: Description of the angle

I’m going to give you outreach information (which includes an asset), and you are to return 6 angles and their associated LinkedIn follow-up message.

The more diverse the outputs are, and creative, the better. You should follow general LinkedIn message practices like keeping it short, concise, and free of fillers such as (”I hope this finds you well”).
Pick 1-3 assets to utilize in your message. In your output say the IDs of the assets you used. Be creative and use them in different ways.

Here's some previous examples of what you're expected to generate.
# Previous Example 1 #
-------------------------------------------------------------

Please generate a follow up LinkedIn message outline for generative outreach to prospects.


## Assets: 
Title: #1 in Demand Generation
Value: Rippling is #1 when it comes to demand generation especially in the tech industry
Tag: Value Prop


## Output:
### Message:
curious - how's demand gen going at Rippling? 🚀
### Angle: Related-based
### Angle Description: Question tangentially related to their work


-------------------------------------------------------------
# Previous Example 2 #
-------------------------------------------------------------

Please generate a follow up LinkedIn message outline for generative outreach to prospects.


## Assets: 
Title: Top Selling Products
Value: Designed top-selling products for Oracle, Intuit, IBM, Cisco, Sharecare, Filezilla, and more
Tag: Social Proof


## Output:
### Message:
Was curious to see what you’re working on. For context, I’ve designed top-selling products for Oracle, Intuit, IBM, and Cisco. Open to talking UX some time [[ prospect first name ]]?
### Angle: Experience-based
### Angle Description: Shares experience to build credibility

-------------------------------------------------------------

# Your Turn #
Okay now it's your turn to generate some messages. Good luck!


Please generate a follow up LinkedIn message outline for generative outreach to prospects.


{context_info}


## General guidelines

- Final note - each message should follow a different structure. Here are some things you can vary on:
    - tone - informal, creative, informational (try different types but avoid being salesy)
    - structure - mix up message approach
- Keep the angles one word, then -based. Such as `Persona-based`
- remember, most people don't like to get flooded with massive messages. Please keep your messages under 3 sentences.



## Assets: 
{assets_str}


## Output:
""".strip()

    print(f"GENERATING LINKEDIN FOLLOW UP")
    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=MESSAGE_MODEL,
            max_tokens=4000,
            type="EMAIL",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    return completion


def generate_linkedin_cta(
    client_id: int,
    archetype_id: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
):

    prompt = f"""
  
You are an angle creator for outbound LinkedIn. Your goal is to return new, creative outbound angles and copy for generative call to actions on generative outreach to prospects.
When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

{additional_prompting}

I will give you 3 few shot examples. Each example contains

- ## Assets
- ## Output: LinkedIn Call to Action
- ## Angle: Angle-based
- ## Angle Description: Description of the angle

I’m going to give you outreach information (which includes an asset), and you are to return 6 angles and their associated LinkedIn call to action.

The more diverse the outputs are, and creative, the better.
Pick 1 asset to utilize in your message. In your output say the IDs of the assets you used. Be creative and use them in different ways.

Here's some previous examples of what you're expected to generate.
# Previous Example 1 #
-------------------------------------------------------------

Please generate a follow up LinkedIn message outline for generative outreach to prospects.


## Assets: 
Title: 95% Demand Generation
Value: AskEdith helps with 95% of demand generation tasks
Tag: Value Prop


## Output:
### Message:
Would love to see if AskEdith would be helpful for you all.
### Angle: Help-based
### Angle Description: Offers help


-------------------------------------------------------------
# Previous Example 2 #
-------------------------------------------------------------

Please generate a follow up LinkedIn message outline for generative outreach to prospects.


## Assets: 
Title: 1000s of Companies
Value: Files bills for 1000s of companies
Tag: Social Proof


## Output:
### Message:
How are you all dealing with billing and the back office?
### Angle: Question-based
### Angle Description: Asks a probing question

-------------------------------------------------------------

# Your Turn #
Okay now it's your turn to generate some messages. Good luck!


Please generate a follow up LinkedIn message outline for generative outreach to prospects.


{context_info}


## General guidelines

- Final note - each message should follow a different structure. Here are some things you can vary on:
    - tone - informal, creative, informational (try different types but avoid being salesy)
    - structure - mix up message approach
- Keep the angles one word, then -based. Such as `Persona-based`
- remember, this should be an ending call to action, so make sure it's clear and concise.



## Assets: 
{assets_str}


## Output:
""".strip()

    print(f"GENERATING LINKEDIN CTA")
    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=MESSAGE_MODEL,
            max_tokens=4000,
            type="EMAIL",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    return completion


# def generate_email_follow_up(
#     client_id: int,
#     archetype_id: int,
#     step_num: int,
#     context_info: str,
#     assets_str: str,
#     additional_prompting: str,
#     previous_emails_str: str,
# ):

#     prompt = f"""


# You are working to create a follow up email in a sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.
# The email should use different assets that have a unique value prop, pain point, case study, unique facts, etc that can be used in to make that email stand out. Each should also have a different angle or approach to the outreach.
# When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

# {additional_prompting if additional_prompting else ""}

# Here's some previous examples of what you're expected to generate.
# # Previous Example 1 #
# -------------------------------------------------------------

# Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

# {get_email_example(1, step_num)}

# -------------------------------------------------------------

# # Previous Example 2 #
# -------------------------------------------------------------

# Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

# {get_email_example(2, step_num)}

# -------------------------------------------------------------

# # Previous Example 3 #
# -------------------------------------------------------------

# Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

# {get_email_example(3, step_num)}

# -------------------------------------------------------------

# # Your Turn #
# Okay now it's your turn to generate an email. Good luck! Remember to keep your email short and concise and stay off the spam folder!


# Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

# {context_info}

# {previous_emails_str}

# {assets_str}


# ## Output:

#     """.strip()

#     print(prompt)

#     completion = (
#         get_text_generation(
#             [
#                 {
#                     "role": "user",
#                     "content": prompt,
#                 }
#             ],
#             model=MESSAGE_MODEL,
#             max_tokens=4000,
#             type="EMAIL",
#             temperature=0.85,
#             use_cache=False,
#         )
#         or ""
#     )

#     return completion


def clean_output_with_ai(output: str):

    prompt = f"""
    
    I'm going to give you some data and I want you to format it in a JSON array format with EXACTLY this structure:
    
    [(
    "angle": <SOMETHING>-based,
    "angle_description": <ANGLE_DESCRIPTION>,
    "subject": <MESSAGE_SUBJECT>,
    "message": <MESSAGE_BODY>,
    "asset_ids": [<ASSET_IDS>],
    )]
    
    If you don't have something, just put an empty string. Maintain the newline formatting in the JSON message. ONLY respond with the JSON array format.
    The message should just be the message body, not the subject line, not the angle, not the angle description, and not the asset IDs.
    
    # Data #
    {output}
    
    """.strip()

    print("CLEANING OUTPUT")
    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=CLEANING_MODEL,
            max_tokens=4000,
            type="MISC_CLASSIFY",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    import yaml

    try:
        return yaml.safe_load(
            completion.replace("```json", "").replace("```", "").strip()
        )
    except:
        print("ERROR", completion)
        return []


def clean_output(output: str):
    parts = output.split("\n### Angle")
    message_raw = parts[0].strip()
    message_parts = message_raw.split("### Message")
    message = (
        message_parts[1].strip() if len(message_parts) > 1 else message_parts[0].strip()
    )
    angle = parts[1].strip() if len(parts) > 1 else "Unknown Angle"

    # Remove potential subject line
    message = re.sub(
        r"^\W*Subject:.+?\n", "", message, 1, flags=re.MULTILINE | re.IGNORECASE
    )

    # Remove potential generation fluff
    message = re.sub(r"^\W+", "", message)
    angle = re.sub(r"^\W+", "", angle)

    return {"message": message, "angle": angle}


def get_email_example(example_num: int, step_num: int):

    def get_example_prompt():
        prompt = ""

        for i in range(1, step_num):

            title = ""

            if i == 1:
                title = "Initial Cold Email"
            else:
                title = f"{rank_number(i)} Follow-Up Email"

            example = get_email_step_example(example_num, i)
            if example is None:
                continue

            prompt += f"""

### {title}:
-----
{example}

            """

        return prompt.strip()

    return f"""
      
{get_example_context_info(example_num)}
      
{get_example_prompt()}
      
      """.strip()


def get_example_context_info(example_num: int):

    # Sarthak Mishra
    if example_num == 1:
        return """
      
Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Your Name: Sarthak Mishra
    
    
    Your Title: We're Hiring! | Founder @ Drool | UI/UX Design, Webflow Development
    Your Bio: Design Strategist, Entrepreneurial Storyteller, Problem Solver. Currently building Drool to simplify design operations for early-stage startups.


It started with a T-shirt business at 19, an early venture that sparked my entrepreneurial spirit. But real learning came later – the kind that textbooks don't teach. My time at NID wasn't just about design; it was a lesson in life's unpredictability and the value of resilience.

Fast-forward to today: My journey has seen me in various roles – starting as an intern at diverse startups, experiencing the ups and downs of being a founder, and now leading as the CEO of Drool. Along the way, I've learned to always anticipate the unexpected and draw lessons from each challenge.

Turning Points:

⭐Internships: Worked with various startups, learning about resilience and the guts needed in entrepreneurship.
⭐Learning from Failures: Each failed venture taught me something new, especially about expecting the unexpected.

What I Bring to Drool:

📌 I've got hands-on experience in growing startups, not just in design but also in marketing and strategy.
📌 I believe in looking beyond the obvious, finding new solutions to old problems.
📌 As a CEO, I focus on solving problems and bringing together people who can think out of the box.

Drool's Vision: At Drool, our mission is clear. We're here to simplify and streamline design operations for early-stage SaaS startups. Our goal is to make effective design accessible to businesses of all sizes, extending our services to scale-ups and beyond.

Engaging with the World: Networking isn't just a business strategy for us; it's the essence of Drool. I thrive on founder-led sales, using each interaction as a learning opportunity, understanding clients not just as businesses but as people with stories.
    Your Job Description: Crafting high-impact Webflow sites and building my dream design agency, brick by brick! → http://trydrool.com
    Your Industry: Design
    Your Location: Ahmedabad, Gujarat, India
    Your School: National Institute of Design
    Your Degree: Foundation degree
    Your Education Field: Graphic Design
    
    
    Your Company Name: Drool
    Your Company Tagline: A single subscription for all your design needs.
    Your Company Description: None
  
  
      """.strip()

    # Ayush Sharma
    if example_num == 2:
        return """
      
Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Your Name: Ayush Sharma
    
    
    Your Title: Founder and CEO of Warp (YC W23) | Making payroll and compliance easy for founders
    Your Bio: Warp is a modern payroll & compliance platform made for founders and remote teams. Checkout Warp at joinwarp.com
    Your Job Description: Building Warp (YC W23) – modern payroll and compliance for startups.
    Your Industry: Computer Software
    Your Location: Brooklyn, New York, United States
    Your School: Massachusetts Institute of Technology
    Your Degree: Master's degree
    Your Education Field: Systems and Machine Learning
    
    
    Your Company Name: Warp
    Your Company Tagline: Payroll and Compliance for Startups.
    Your Company Description: Payroll built for startups. Put state tax registrations on autopilot. Never waste time on payroll operations again.

      """.strip()

    # Will Han
    if example_num == 3:
        return """

Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Your Name: Will Han
    
    Your Title: Co-Founder @ BitSync
    Your Bio: Making something great with AI
    Your Industry: Computer Software
    Your Location: Los Angeles, California, United States
    Your School: Harvard University
    Your Degree: Master's degree
    Your Education Field: System engineering and Machine Learning
    
    
    
    Your Company Name: BitSync
    Your Company Tagline: Train and deploy your AI models within minutes!
    Your Company Description: BitSync provides unparalleled access to GPUs for deep learning at massive scale, with high-speed and adaptable infrastructure
  
      
      """.strip()

    return ""


def get_email_step_example(example_num: int, step_num: int):

    # Sarthak Mishra
    if example_num == 1:
        if step_num == 1:
            return f"""
        
## Assets: 
Title: Hiring Designers is a Huge Hassle
Value: Hiring designers is a huge hassle. Startup founders often have to juggle between other priorities as design. Designers can also be hard to find due to their “full stack” capabilities across product, marketing, different tools, and more.
Tag: Pain Point


## Output:
### Message:
Hi [[ prospect first name ]],

I know that finding top-tier Designers can be a hassle, especially when you factor in the risks and the high costs of hiring and (if needed) firing.

To add to it, you’ll have to juggle between hiring product designers, graphic designers, web designers, and more which will only multiply the problems even further. Even if you do manage to get through all these challenges, retaining these "Top-Tier" Designers is a struggle in itself.

If you've experienced these problems at [[ prospect company ]], then we here at Drool have the perfect solution.

Would it be okay if I shared some more info? Or maybe there's someone else on your team who'd be the right fit for this conversation?

Thank you for your time, and I look forward to hearing from you.

Regards,
Sarthak Mishra
CEO @ Drool
### Angle: Narrative-based
### Angle Description: Come up with a narrative that someone can resonate with
        
        """.strip()

        if step_num == 2:
            return f"""""".strip()

        if step_num == 3:
            return f"""""".strip()

    # Ayush Sharma
    if example_num == 2:
        if step_num == 1:
            return f"""
          
## Assets: 
Title: Payroll Compliance Takes Weeks
Value: Compliance takes weeks to complete for founders and is often cumbersome, complex, and hard to navigate.
Tag: Pain Point

Title: Easy to migrate
Value: Migrating from Rippling, Gusto, or Dee takes 15 minutes
Tag: Value Prop


## Output:
### Message:
Hi [[ prospect first name ]],

Imagine if you could skip weeks of frustrating payroll and compliance paperwork.

With Warp, you can bypass weeks of tedious paperwork as all your tasks, like opening and managing payroll tax accounts, filing submissions, and setting up unemployment insurance rates are handled automatically.

If you're migrating from Rippling, Gusto, or Deel, a quick 15-minute call is all it takes for onboarding and migration.

Would love to show you Warp if you have some time this week, could you let me know some times?

Best,
Ayush
### Angle: Imagination-based
### Angle Description: Show what a world would look like with us
          
        """.strip()

        if step_num == 2:
            return f"""""".strip()

        if step_num == 3:
            return f"""""".strip()

    # Will Han
    if example_num == 3:
        if step_num == 1:
            return f"""
          
## Assets: 
Title: Lowest Price
Value: Bitsync provides the lowest price amongst providers, sets up your instance instantly, and gives free trials
Tag: Value Prop


## Output:
### Message:
Hi [[ prospect first name ]],

My name is Will Han, and I’m a cofounder of BitSync. We are a low-cost GPU Cloud and training platform that is easy to migrate to.

Key advantages of BitSync Cloud are:

- Guaranteed lowest price amongst cloud providers
- Free instance time to transfer your setup (i.e. billing doesn’t start until your model/data are uploaded and drivers are installed)
- Free ingress/egress + storage
We build complementary infrastructure for your unique needs (e.g. distributed computing, etc)
- Free trials + credits for new customers

If you are interested or have any questions, just let me know. Looking forward to hearing from you!

Best,
Will
### Angle: Advantage-based
### Angle Description: Bullet point format, plain and simple

        """.strip()

        if step_num == 2:
            return f"""""".strip()

    return None
