from app import db

from flask import Blueprint, jsonify, request
from src.prospecting.models import ProspectStatus
from src.prospecting.services import (
    batch_mark_prospects_as_sent_outreach,
    create_prospect_from_linkedin_link,
    create_prospects_from_linkedin_link_list,
    prospect_exists_for_archetype,
    update_prospect_status,
)
from src.client.models import ClientArchetype
from src.client.services import get_client_archetype
from src.prospecting.clay_run.clay_run_prospector import ClayRunProspector
from src.prospecting.clay_run.configs import ProspectingConfig
from src.utils.request_helpers import get_request_parameter
from src.prospecting.services import (
    batch_update_prospect_statuses,
    mark_prospect_reengagement,
)

from tqdm import tqdm

from src.utils.random_string import generate_random_alphanumeric

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)


@PROSPECTING_BLUEPRINT.route("/", methods=["POST"])
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
    client_id = ca.client_id

    prospector: ClayRunProspector = ClayRunProspector()

    config: ProspectingConfig = ProspectingConfig(
        location=location, headline=headline, industry=industry, experience=experience
    )

    prospects = prospector.prospect_sync(prospecting_config=config)

    batch_id = generate_random_alphanumeric(32)

    print("Uploading unique prospects to database...")
    for prospect in tqdm(prospects):
        linkedin_url = prospect["Linkedin"]
        prospect_exists = prospect_exists_for_archetype(
            linkedin_url=linkedin_url, client_id=client_id
        )

        from src.prospecting.models import Prospect

        if not prospect_exists and prospect["Full Name"]:
            p: Prospect = Prospect(
                client_id=client_id,
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
                batch=batch_id,
                status=ProspectStatus.PROSPECTED,
            )
            db.session.add(p)
            db.session.commit()
    print("Done uploading!")

    return jsonify({"data": prospects, "batch_id": batch_id})


@PROSPECTING_BLUEPRINT.route("/", methods=["PATCH"])
def update_status():
    from model_import import ProspectStatus

    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    new_status = ProspectStatus[
        get_request_parameter("new_status", request, json=True, required=True)
    ]

    success = update_prospect_status(prospect_id=prospect_id, new_status=new_status)

    if success:
        return "OK", 200

    return "Failed to update", 400


@PROSPECTING_BLUEPRINT.route("/from_link", methods=["POST"])
def prospect_from_link():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    url = get_request_parameter("url", request, json=True, required=True)

    batch = generate_random_alphanumeric(32)
    success = create_prospect_from_linkedin_link(
        archetype_id=archetype_id, url=url, batch=batch
    )

    if success:
        return "OK", 200
    return "Failed to create prospect", 404


@PROSPECTING_BLUEPRINT.route("/from_link_chain", methods=["POST"])
def prospect_from_link_chain():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    url_string = get_request_parameter("url_string", request, json=True, required=True)

    success = create_prospects_from_linkedin_link_list(
        url_string=url_string, archetype_id=archetype_id
    )

    if success:
        return "OK", 200
    return "Failed to create prospect", 404


@PROSPECTING_BLUEPRINT.route("/batch_mark_sent", methods=["POST"])
def batch_mark_sent():
    updates = batch_mark_prospects_as_sent_outreach(
        prospect_ids=get_request_parameter(
            "prospect_ids", request, json=True, required=True
        ),
        client_sdr_id=get_request_parameter(
            "client_sdr_id", request, json=True, required=True
        ),
    )
    return jsonify({"updates": updates})


@PROSPECTING_BLUEPRINT.route("/batch_update_status", methods=["POST"])
def batch_update_status():
    success = batch_update_prospect_statuses(
        updates=get_request_parameter("updates", request, json=True, required=True)
    )
    if success:
        return "OK", 200

    return "Failed to update", 400


@PROSPECTING_BLUEPRINT.route("/mark_reengagement", methods=["POST"])
def mark_reengagement():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    success = mark_prospect_reengagement(prospect_id=prospect_id)
    if success:
        return "OK", 200
    return "Failed to update", 400
