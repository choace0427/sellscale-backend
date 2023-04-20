from ctypes import Union
from model_import import Prospect, Client, ClientArchetype
from src.ml.openai_wrappers import (
    wrapped_create_completion,
    CURRENT_OPENAI_CHAT_GPT_MODEL,
)
import json


def generate_research(prompt: str, retries: int):
    attempts = 0
    while attempts < retries:
        json_str = wrapped_create_completion(
            prompt=prompt, model=CURRENT_OPENAI_CHAT_GPT_MODEL, max_tokens=1000
        )
        research = json.loads(json_str)
        if research:
            break
        attempts += 1
    return research


def generate_prospect_research(
    prospect_id: int, print_research: bool = False
) -> tuple[str, list]:
    """
    Given a prospect ID, this will generate a research report for the prospect that
    contains 3-4 bullet points of information about the prospect and why
    they are a good fit for the company that is selling the product.

    Return prompt and array of research points
    """
    prompt = get_research_generation_prompt(prospect_id)
    research = generate_research(prompt=prompt, retries=3)

    try:
        if print_research:
            print("**Prompt:**\n---\n", prompt, "\n---\n\n", "**Research:**\n")
            for point in research:
                print("- ", point["title"], ": ", point["reason"])
    except:
        print("Error printing research")

    return prompt, research


def get_research_generation_prompt(prospect_id: int) -> str:
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_id = prospect.client_id
    client: Client = Client.query.get(client_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    prospect_name = prospect.full_name
    prospect_title = prospect.title
    prospect_bio = prospect.linkedin_bio
    # only get first 250 characters of bio and first paragraph
    prospect_bio = prospect_bio[:250].split("\n")[0] if prospect_bio else ""

    prospect_company = prospect.company

    company_name = client.company
    prospect_archetype = client_archetype.archetype
    company_tagline = client.tagline
    archetype_value_prop = client_archetype.persona_fit_reason

    prompt: str = """Prospect Information:
- full name: {prospect_name}
- title: {prospect_title}
- bio: {prospect_bio}
- company: {prospect_company}

Product Information:
- company name: {company_name}
- persona selling to: {prospect_archetype}
- company tagline: {company_tagline}
- archetype value prop: {archetype_value_prop}

You are a sales account research assistant. Using the information about the Prospect and Product, explain why the prospect would be a good fit for buying the product. 

Generate a javascript array of objects. Each object should have two elements: title and reason. Keep titles to 2-4 words in length maximum. Keep reasons short, to 1 sentence maximum.

JSON payload:""".format(
        prospect_name=prospect_name,
        prospect_title=prospect_title,
        prospect_bio=prospect_bio,
        prospect_company=prospect_company,
        company_name=company_name,
        prospect_archetype=prospect_archetype,
        company_tagline=company_tagline,
        archetype_value_prop=archetype_value_prop,
    )

    return prompt
