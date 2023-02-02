from app import db

from flask import Blueprint, request, jsonify
from src.message_generation.services import (
    batch_generate_prospect_emails,
    mark_prospect_email_approved,
)
from src.email_outbound.services import create_email_schema, batch_update_emails
from src.email_outbound.outreach_io.services import *
from src.utils.request_helpers import get_request_parameter
from src.message_generation.services import batch_mark_prospect_email_sent
from tqdm import tqdm
from src.message_generation.services import (
    wipe_prospect_email_and_generations_and_research,
)

EMAIL_GENERATION_BLUEPRINT = Blueprint("email_generation", __name__)


@EMAIL_GENERATION_BLUEPRINT.route("/create_email_schema", methods=["POST"])
def post_create_email_schema():
    name = get_request_parameter("name", request, json=True, required=True)
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )

    email_schema = create_email_schema(
        name=name, client_archetype_id=client_archetype_id
    )
    if email_schema:
        return "OK", 200
    return "Could not create email schema.", 400


@EMAIL_GENERATION_BLUEPRINT.route("/batch", methods=["POST"])
def index():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )
    email_schema_id = get_request_parameter(
        "email_schema_id", request, json=True, required=True
    )

    batch_generate_prospect_emails(
        prospect_ids=prospect_ids, email_schema_id=email_schema_id
    )

    return "OK", 200


@EMAIL_GENERATION_BLUEPRINT.route("/approve", methods=["POST"])
def approve():
    prospect_email_id = get_request_parameter(
        "prospect_email_id", request, json=True, required=True
    )

    success = mark_prospect_email_approved(prospect_email_id=prospect_email_id)
    if success:
        return "OK", 200
    return "Could not approve email.", 400


@EMAIL_GENERATION_BLUEPRINT.route("/batch/mark_sent", methods=["POST"])
def batch_mark_sent():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    batch_mark_prospect_email_sent(prospect_ids=prospect_ids)

    return "OK", 200


@EMAIL_GENERATION_BLUEPRINT.route("/wipe_prospect_email_and_research", methods=["POST"])
def wipe_prospect_email_and_research():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    success = wipe_prospect_email_and_generations_and_research(prospect_id=prospect_id)
    if success:
        return "OK", 200
    return "Failed to wipe", 400


@EMAIL_GENERATION_BLUEPRINT.route("/batch_update_emails", methods=["POST"])
def post_batch_update_emails():
    payload: dict = get_request_parameter("payload", request, json=True, required=True)
    success, message = batch_update_emails(payload=payload)
    if success:
        return message, 200
    return message, 400


@EMAIL_GENERATION_BLUEPRINT.route("/update_status/csv", methods=["POST"])
def update_status_from_csv_payload():
    csv_payload: list = get_request_parameter("csv_payload", request, json=True, required=True)    
    client_id: int = get_request_parameter("client_id", request, json=True, required=True)

    validated, message = validate_outreach_csv_payload(csv_payload)
    if not validated:
        return message, 400

    update_status_from_csv.delay(payload=csv_payload, client_id=client_id)

    return "Status update is in progress", 200