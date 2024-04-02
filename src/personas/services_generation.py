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
from src.utils.datetime.dateutils import get_current_time_casual
from src.individual.services import parse_work_history


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
        f"""You Company Tagline: {client.tagline}""" if client.tagline else ""
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
    sdr_work_history = (
        "Your Work History: \n"
        + "\n".join(
            [
                f"History - Company Name: {work.get('company_name')}, Title: {work.get('title')}, Start Date: {work.get('start_Date', '?')}, End Date: {work.get('start_Date', '?')}"
                for work in parse_work_history(individual.work_history)
            ]
        )
        if individual.work_history
        else ""
    )

    day, day_of_month, month, year = get_current_time_casual(sdr.timezone)

    context_info = f"""
Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Current Time: {day}, {day_of_month}, {month}, {year}
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
    {sdr_work_history}
    """.strip()

    return context_info


def generate_sequence(
    client_id: int,
    archetype_id: int,
    sequence_type: str,
    num_steps: int,
    additional_prompting: str,
):

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    context_info = get_sdr_prompting_context_info(archetype.client_sdr_id)

    raw_assets = get_archetype_assets(archetype_id)
    assets = [
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

    assets_str = "## Assets: \n" + "\n\n".join(
        [
            f"Title: {asset.get('title')}\nValue: {asset.get('value')}\nTag: {asset.get('tag')}"
            for asset in assets
        ]
    )

    if sequence_type == "EMAIL":
        return generate_email_steps(
            client_id=client_id,
            archetype_id=archetype_id,
            num_steps=num_steps,
            context_info=context_info,
            assets_str=assets_str,
            additional_prompting=additional_prompting,
        )

    return None


def generate_email_steps(
    client_id: int,
    archetype_id: int,
    num_steps: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
):

    prompt = f"""
    
You are working to create a sequence of emails for generative outreach to prospects. The first email will be a cold email, and the following emails will be follow-ups to the cold email if the prospect does not respond.
Each email should use different assets that have a unique value prop, pain point, case study, unique facts, etc that can be used in to make that email stand out. Each should also have a different angle or approach to the outreach.
When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

{additional_prompting if additional_prompting else ""}

Here's a previous example of what you're expected to generate.
# Previous Example #
-------------------------------------------------------------

Please generate a 3 email sequence for generative outreach to prospects. The first email will be a cold email, and the following emails will be follow-ups to the cold email if the prospect does not respond.

Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Current Time: Monday, 1st, April, 2024
    Your Name: Jonathan Herzog
    Your Website: jonathanherzogcoach.com
    
    Your Title: Executive Coach
    Your Bio: Hey! I'm a full-stack software engineer with a focus on web development, AI, and systems engineering.
    
    Your Industry: Computer Software
    Your Location: San Francisco, California, United States
    Your School: Southern Oregon University
    Your Degree: Bachelor of Science - BS
    Your Education Field: Computer Science
    Your Education Start Date: 2019-09-01
    Your Education End Date: 2021-06-01
    Your Company Name: Board of Innovation
    You Company Tagline: Board of Innovation is a global innovation consultancy for large brands.
    Your Company Description: Board of Innovation is a global innovation firm, imagining tomorrow’s products, services and businesses – and creating them today. Their three areas of consulting are "making bigger moves", "designing new experiences", and "launching new businesses".
 

    Your Company Key Value Props: - Board of Innovation has worked with top clients like Roche, Pandora, Canon, and Nestle to launch and innovate on their business lines
- Board of Innovation recently launched Creative AI - leveraging GPT in modern enterprises for innovation
- Board of Innovation is one of the top global innovation firms for leading, innovative companies
    Your Company Mission: We are a global innovation firm. Imagining tomorrow's products, services and businesses - and creating them today.
    
    Your Work History: 
History - Company Name: SellScale, Title: Founding Software Engineer, Start Date: ?, End Date: ?
History - Company Name: Wanderer's Guide, Title: Founder, Start Date: ?, End Date: ?
History - Company Name: Sun West Mortgage Company, Inc., Title: Software Engineer, Start Date: ?, End Date: ?
History - Company Name: TalesTerrain, Title: Founder, Start Date: ?, End Date: ?
History - Company Name: FlexSweep Industries, Title: Software Engineer, Start Date: ?, End Date: ?
History - Company Name: Springs, Title: Software Developer, Start Date: ?, End Date: ?
History - Company Name: WalkAshland, Title: Java/Kotlin Software Developer, Start Date: ?, End Date: ?
History - Company Name: The Gamer's Den, Title: Web Developer, Start Date: ?, End Date: ?
History - Company Name: Southern Oregon University, Title: Computer Science Tutor, Start Date: ?, End Date: ?


## Assets: 
Title: 24-hour promotion; expires Jan 4
Value: <p>We have a 24 hour promotion where any new user will get 1,000+ free email credits, today!</p><p>It's limited time, they should sign up soon.</p><p>Expires Jan 4th, 2024.</p>
Tag: Offer

Title: First Sales tool using GPT-v
Value: <p>SellScale uses GPT-V for several use cases like scheduling + research.</p><p>This is the first of it's kind in the sales space.</p>
Tag: Research

Title: Sign up today!
Value: <p>Sign up at sellscale.com</p>
Tag: Offer

Title: Hedge Fund Market Research
Value: NewtonX offers custom expert surveys to hedge funds, providing industry intelligence at scale. By utilizing AI and automation-driven research technology, investors can reach a larger sample within a shorter time frame. The surveys help answer key business questions and allow for quicker and more confident investment decisions.
Tag: Research


## Output:



-------------------------------------------------------------

# Your Turn #
Okay now it's your turn to generate an email sequence. Good luck!



Please generate a {num_steps} email sequence for generative outreach to prospects. The first email will be a cold email, and the following emails will be follow-ups to the cold email if the prospect does not respond.

{context_info}


{assets_str}


## Output:

    """.strip()

    print(prompt)

    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-4-turbo-preview",
            max_tokens=4000,
            type="CLIENT_ASSETS",
            use_cache=True,
        )
        or ""
    )

    return completion
