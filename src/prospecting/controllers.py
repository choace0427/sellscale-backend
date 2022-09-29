from app import db

from flask import Blueprint, jsonify, request
from src.prospecting.services import prospect_exists_for_archetype
from src.client.models import ClientArchetype
from src.client.services import get_client_archetype
from src.prospecting.clay_run.clay_run_prospector import ClayRunProspector
from src.prospecting.clay_run.configs import ProspectingConfig
from src.utils.request_helpers import get_request_parameter

from tqdm import tqdm

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)


@PROSPECTING_BLUEPRINT.route("/")
def index():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    location = get_request_parameter("location", request, json=True, required=True)
    headline = get_request_parameter("headline", request, json=True, required=True)
    industry = get_request_parameter("industry", request, json=True, required=True)
    experience = get_request_parameter("experience", request, json=True, required=True)

    ca: ClientArchetype = get_client_archetype(client_archetype_id=archetype_id)
    if not ca:
        return "Archetype not found", 404

    prospector: ClayRunProspector = ClayRunProspector()

    config: ProspectingConfig = ProspectingConfig(
        location=location, headline=headline, industry=industry, experience=experience
    )

    prospects = prospector.prospect_sync(prospecting_config=config)

    print("Uploading unique prospects to database...")
    for prospect in tqdm(prospects):
        linkedin_url = prospect["Linkedin"]
        prospect_exists = prospect_exists_for_archetype(
            linkedin_url=linkedin_url, archetype_id=archetype_id
        )

        from src.prospecting.models import Prospect

        if not prospect_exists:
            p: Prospect = Prospect(
                archetype_id=archetype_id,
                company=prospect["Company"],
                company_url=prospect["Company URL"],
                employee_count=prospect["Employee Count"],
                full_name=prospect["Full Name"],
                industry=prospect["Industry"],
                linkedin_url=prospect["Linkedin"],
                linkedin_bio=prospect["Linkedin Bio"],
                title=prospect["Title"],
                twitter_url=prospect["Twitter"],
            )
            db.session.add(p)
            db.session.commit()
    print("Done uploading!")

    return jsonify({"data": prospects})
