from sqlalchemy import func
from src.ml.openai_wrappers import (
    OPENAI_COMPLETION_DAVINCI_3_MODEL,
    wrapped_create_completion,
)
from app import celery
from src.prospecting.models import Prospect
from src.client.services import create_client_archetype
from model_import import ClientSDR, ClientArchetype
import json
import yaml


@celery.task
def create_unassigned_contacts_archetype(client_sdr_id: int) -> tuple[bool, str]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"

    unassigned_contacts_client_archetypes: list[ClientArchetype] = (
        ClientArchetype.query.filter_by(
            client_sdr_id=client_sdr_id, is_unassigned_contact_archetype=True
        ).all()
    )
    if len(unassigned_contacts_client_archetypes) >= 1:
        return False, "Unassigned Contacts Archetype already exists"

    data = create_client_archetype(
        client_id=client_sdr.client_id,
        client_sdr_id=client_sdr_id,
        archetype="{name}'s Unassigned Contacts".format(name=client_sdr.name),
        is_unassigned_contact_archetype=True,
        filters=[],
        active=False,
    )
    client_archetype_id = data and data["client_archetype_id"]

    return True, "Unassigned Contacts archetype created with id #{id}".format(
        id=client_archetype_id
    )


def predict_persona_buckets_from_client_archetype(client_archetype_id: int):
    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not archetype:
        return False, "Client Archetype not found"

    prospects: Prospect = (
        Prospect.query.filter_by(archetype_id=client_archetype_id)
        .order_by(func.random())
        .limit(100)
        .all()
    )
    if not prospects:
        return False, "No prospects found"

    list_of_prospect_titles = [prospect.title for prospect in prospects]
    concatenated_list_of_prospect_titles = "\n".join(list_of_prospect_titles)

    raw_open_ai_categorization = wrapped_create_completion(
        model=OPENAI_COMPLETION_DAVINCI_3_MODEL,
        max_tokens=500,
        prompt="""
You are a sales researcher. Given a list of prospect titles, create 3-5 personas that I should bucket these prospects into. I would like a list of personas with the following information for each persona:
- Persona Name: a short name for the persona (i.e. C-Suite Leadership, VPs in Manufacturing, Directors, etc.)
- Persona Tagline: a short tagline for the persona (i.e. C-Suite Leadership are the decision makers in the company)
- Persona Description: a short description of the persona (1-2 sentence max) (i.e. C-Suite Leadership are the decision makers in the company. They are responsible for the overall strategy and direction of the company.)
- Example Titles: list 3 titles that would fit into this persona (i.e. VP of Sales, Director of Marketing, etc.)

Personas:
{prospect_titles}

Output:""".format(
            prospect_titles=concatenated_list_of_prospect_titles
        ),
    )

    json_open_ai_categorization = wrapped_create_completion(
        model=OPENAI_COMPLETION_DAVINCI_3_MODEL,
        max_tokens=600,
        prompt="""
Given a list of persona names, descriptions, and titles, return a JSON array of objects. Each object should have the following properties:
- name: str. the name of the persona
- tagline: str. the tagline of the persona
- description: str. the description of the persona
- example_titles: list. a list of example titles that fit into this persona

Raw Data:
{raw_data}

JSON data:
    """.format(
            raw_data=raw_open_ai_categorization
        ),
    )

    data = yaml.safe_load(json_open_ai_categorization)

    return True, data
