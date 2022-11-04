from app import db

from flask import Blueprint, request, jsonify
from src.message_generation.services import (
    batch_generate_prospect_emails,
    mark_prospect_email_approved,
)
from src.email_outbound.services import create_email_schema
from src.utils.request_helpers import get_request_parameter
from tqdm import tqdm

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
