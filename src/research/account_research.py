from typing import Optional
from model_import import Prospect, Client, ClientArchetype, ClientSDR
from src.ml.openai_wrappers import (
    wrapped_create_completion,
    wrapped_chat_gpt_completion_with_history,
    OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
)
import json
import yaml
from model_import import AccountResearchType, AccountResearchPoints
from app import db, celery
from src.utils.abstract.attr_utils import deep_get


def run_research_extraction_for_prospects_in_archetype(
    archetype_id: int,
    hard_refresh: bool = False,
):
    """
    Runs research extraction for all prospects in an archetype

    Args:
        archetype_id (int): the archetype ID
        hard_refresh (bool, optional): whether to hard refresh the research points. Defaults to False.
    """
    prospects: list[Prospect] = Prospect.query.filter_by(
        archetype_id=archetype_id
    ).all()
    for prospect in prospects:
        # todo(Aakash) add credits system here to prevent abuse
        generate_prospect_research.delay(prospect.id, False, hard_refresh)
    return True


def generate_generic_research(prompt: str, retries: int):
    """
    Generates generic research and outputs a JSON array of objects

    Each object should have two elements: source and reason

    Return Value:
    [
        {
            "source": "source",
            "reason": "reason"
        },
        {
        ...
        }
    ]
    """
    attempts = 0
    while attempts < retries:
        try:
            json_str = wrapped_create_completion(
                prompt=prompt, model=OPENAI_CHAT_GPT_3_5_TURBO_MODEL, max_tokens=1000
            )
            research = yaml.safe_load(json_str)
            if research:
                break
        except:
            attempts += 1
    return research


@celery.task(bind=True, max_retries=3)
def generate_prospect_research(
    self, prospect_id: int, print_research: bool = False, hard_refresh: bool = False
) -> tuple[str, list]:
    """
    Given a prospect ID, this will generate a research report for the prospect that
    contains 3-4 bullet points of information about the prospect and why
    they are a good fit for the company that is selling the product.

    Return prompt and array of research points
    """
    try:
        account_research_points = AccountResearchPoints.query.filter_by(
            prospect_id=prospect_id
        ).all()
        if not hard_refresh and account_research_points:
            return "", []

        if hard_refresh:
            for account_research_point in account_research_points:
                db.session.delete(account_research_point)
            db.session.commit()

        # Check credit usage
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
        if client_sdr.ml_credits <= 0:
            return "", [{"source": "ML Credits", "reason": "Out of ML credits"}]

        prompt = get_research_generation_prompt(prospect_id)
        _, research = generate_research(prospect_id, retries=3)

        try:
            if print_research:
                print("**Prompt:**\n---\n", prompt, "\n---\n\n", "**Research:**\n")
                for point in research:
                    print("- ", point["source"], ": ", point["reason"])
        except:
            print("Error printing research")

        # Charge credits
        client_sdr.ml_credits -= 1
        db.session.commit()

        for point in research:
            account_research_point: AccountResearchPoints = AccountResearchPoints(
                prospect_id=prospect_id,
                account_research_type=AccountResearchType.CHATGPT_CHAIN_RESEARCH,
                title=point["source"],
                reason=point["reason"],
            )
            db.session.add(account_research_point)
        db.session.commit()

        return prompt, research
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def generate_research(
    prospect_id: int, retries: Optional[int] = 0
) -> tuple[bool, dict]:
    """Generates sophisticated research on a Prospect through ChatGPT API chaining.

    Chaining steps:
    1. Use prospect, archetype & company info to create a 'research report'
    2. Condense the research report into research points
    3. Convert research points into JSON format

    Args:
        prospect_id (int): the prospect ID
        retries (Optional[int], optional): the number of retries. Defaults to 0.

    Returns:
        tuple[bool, dict]: success status and research points
    """

    print("got here")

    attempts = 0
    while attempts < retries:
        try:
            # Get paragraph
            history, completion = get_research_paragraph_form(prospect_id)

            # Get bullet points
            history, completion = get_research_bullet_form(prospect_id, history)

            # Get JSON
            history, completion = get_research_json(history)

            research = yaml.safe_load(completion)
            return True, research
        except:
            attempts += 1
            continue

    return False, {}


def get_research_paragraph_form(prospect_id: int) -> tuple[list, str]:
    """Gets research on a Prospect in paragraph form.

    Args:
        prospect_id (int): the prospect ID

    Returns:
        tuple[list, str]: chat history and research paragraph
    """
    from src.research.linkedin.services import get_research_payload_new

    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return ""

    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    if not archetype:
        return ""

    sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    if not sdr:
        return ""

    client: Client = Client.query.get(sdr.client_id)
    if not client:
        return ""

    research_payload = get_research_payload_new(prospect_id)
    company_tagline = deep_get(research_payload, "company.details.tagline")
    company_description = deep_get(research_payload, "company.details.description")
    company_size = deep_get(research_payload, "company.details.staff.total") or ""
    company_size = str(company_size) + " employees" if company_size else ""

    prompt: str = (
        """I am a sales researcher who is identifying why the prospect company would be interested in purchasing my company, {sdr_company_name}'s, product or service.

This is what my company, {sdr_company_name}, does:
- tagline: {sdr_company_tagline}
- description: {sdr_company_description}

I am selling to a prospect named '{prospect_name}' who works at a company called '{prospect_company_name}'. Here is information about the prospect and the account I am selling to:
- Prospect Name: {prospect_name}
- Prospect Title: {prospect_title}
- Prospect Persona: {prospect_persona_name}
- Prospect Bio: {prospect_bio}
- Persona Buy Reason: {prospect_persona_buy_reason}
- Company Name: {prospect_company_name}
- Company Tagline: {prospect_company_tagline}
- Company Description: {prospect_company_description}
- Company Size: {prospect_company_size}

Based on this information, give me a detailed report as to why {prospect_name} and {prospect_company_name} would want to buy {sdr_company_name}'s product.

Ensure you relate each point to {prospect_name} and {prospect_company_name} and be very specific.""".format(
            sdr_company_name=client.company,
            sdr_company_tagline=client.tagline,
            sdr_company_description=client.description,
            prospect_name=prospect.full_name,
            prospect_title=prospect.title,
            prospect_persona_name=archetype.archetype,
            prospect_bio=prospect.linkedin_bio,
            prospect_persona_buy_reason=archetype.persona_fit_reason,
            prospect_company_name=prospect.company,
            prospect_company_tagline=company_tagline,
            prospect_company_description=company_description,
            prospect_company_size=company_size,
        )
    )

    history, completion = wrapped_chat_gpt_completion_with_history(
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=512,
        temperature=0.65,
        # model=OPENAI_CHAT_GPT_4_MODEL,
    )

    return history, completion


def get_research_bullet_form(prospect_id: int, history: list) -> tuple[list, str]:
    """Converts a research paragraph into bullet points. Research paragraph needs to be contained in history.

    Args:
        prospect_id (int): the prospect ID
        history (list): The history of messages

    Returns:
        tuple[list, str]: chat history and research bullet points
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return ""

    client: Client = Client.query.get(prospect.client_id)
    if not client:
        return ""

    prompt = """Convert this report into a set of 4-6 highly specific research points
- Each research point needs a 'source' and 'reason'
- Each research point must explicitly mention {prospect_name} and/or {prospect_company_name}, with high priority given to {prospect_name}.
- The source is a one to two word phrase that describes where the information may have come from.
- The reason is a short sentence that synthesizes why {prospect_name} and {prospect_company_name} should buy {sdr_company_name}'s product.

Follow the format:
- Source: source
- Reason: reason

Keep the bullet points short and concise while ensuring that they are highly specific to {prospect_name} and {prospect_company_name}.
    """.format(
        sdr_company_name=client.company,
        prospect_name=prospect.full_name,
        prospect_company_name=prospect.company,
    )

    history, completion = wrapped_chat_gpt_completion_with_history(
        messages=[
            {"role": "user", "content": prompt},
        ],
        history=history,
        max_tokens=512,
        temperature=0.65,
        # model=OPENAI_CHAT_GPT_4_MODEL,
    )

    return history, completion


def get_research_json(history: list) -> tuple[list, str]:
    """Converts a research paragraph into a JSON object. Research paragraph needs to be contained in history.

    Args:
        history (list): The history of messages

    Returns:
        tuple[list, str]: chat history and research JSON object
    """

    prompt: str = """Convert these research points into a JSON object.

    The JSON object should be a list of dictionaries, with each dictionary containing a 'source' and 'reason' key.

    The format for the JSON object should be as follows:

    [
        {
            "source": "source",
            "reason": "reason"
        },
    ]
    """

    history, completion = wrapped_chat_gpt_completion_with_history(
        messages=[
            {"role": "user", "content": prompt},
        ],
        history=history,
        max_tokens=512,
        temperature=0.65,
        # model=OPENAI_CHAT_GPT_4_MODEL,
    )

    return history, completion


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

    prompt: str = (
        """Prospect Information:
- prospect's full name: {prospect_name}
- prospect's title: {prospect_title}
- prospect's bio: {prospect_bio}
- prospect's company: {prospect_company}

Our Product Information:
- the company name: {company_name}
- the persona we're selling to: {prospect_archetype}
- the company tagline: {company_tagline}
- why this persona would buy this product: {archetype_value_prop}

You are a sales account research assistant. Using the information about the Prospect and Product, explain why the prospect would be a good fit for buying the product.

Generate a javascript array of objects. Each object should have two elements: source and reason. In source, label which prospect information you used to gather the data point. Keep reasons short, to 1 sentence maximum.

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
    )

    return prompt


def get_account_research_points_by_prospect_id(
    prospect_id: int,
) -> list[dict]:
    account_research_points: list[AccountResearchPoints] = (
        AccountResearchPoints.query.filter_by(prospect_id=prospect_id).all()
    )
    return [arp.to_dict() for arp in account_research_points]


def get_account_research_points_inputs(archetype_id: int):
    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    client_id: int = client_archetype.client_id
    client: Client = Client.query.get(client_id)

    return {
        "company": client.company,
        "persona": client_archetype.archetype,
        "company_tagline": client.tagline,
        "persona_value_prop": client_archetype.persona_fit_reason,
    }
