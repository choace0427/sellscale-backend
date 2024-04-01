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


def generate_sequence(
    client_id: int,
    archetype_id: int,
    sequence_type: str,
    num_steps: int,
    additional_prompting: str,
):

    client: Client = Client.query.get(client_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
    individual: Individual = Individual.query.get(sdr.individual_id)

    sdr_name = f"""Your Name: {individual.full_name}"""
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

    print(parse_work_history(individual.work_history))

    day, day_of_month, month, year = get_current_time_casual(sdr.timezone)

    print(day, day_of_month, month, year)

    context_info = f"""
    ## Context:
    {client_name}
    {client_tagline}
    {client_description}
    {client_key_value_props}
    {client_mission}
    {client_impressive_facts}
    """

    raw_assets = get_archetype_assets(archetype_id)
    assets = [
        {
            "id": asset.get("id"),
            "title": asset.get("asset_key"),
            "value": asset.get("asset_key"),
            "tag": (
                asset.get("asset_tags", [])[0]
                if len(asset.get("asset_tags", [])) > 0
                else ""
            ),
        }
        for asset in raw_assets
    ]
    print(assets)

    if sequence_type == "EMAIL":
        return generate_email_steps(
            client_id=client_id,
            archetype_id=archetype_id,
            num_steps=num_steps,
            assets=assets,
            additional_prompting=additional_prompting,
        )

    return None


def generate_email_steps(
    client_id: int,
    archetype_id: int,
    num_steps: int,
    assets: list[dict[str, str]],
    additional_prompting: str,
):

    prompt = f"""
    
You are working with a company to generate concise  to create a series of marketing assets for them. These assets are unique value props, pain points, case studies, unique facts, etc that can be used in marketing outreach.
You will be provided with some general information to give context about the client and then you will be provided a text dump.
Please use the text dump to create at least 3 value prop-based marketing assets, 3 pain point-based marketing assets, 2 case study-based marketing assets, 2 unique fact-based marketing assets, and as many as possible phrase or template marketing assets.
If you're unable to meet that criteria, it's okay. Just do your best and prioritize concise quality assets over quantity.

{additional_prompting if additional_prompting else ""}

Here's a previous example of what you're expected to generate.
# Previous Example #

    """.strip()

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

    return
