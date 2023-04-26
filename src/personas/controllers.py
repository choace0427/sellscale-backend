from src.authentication.decorators import require_user
from app import db

from flask import Blueprint, jsonify, request
from src.personas.services import (
    create_persona_split_request,
    get_recent_split_requests,
    get_split_request_details,
)
from src.utils.request_helpers import get_request_parameter

PERSONAS_BLUEPRINT = Blueprint("personas", __name__)


@PERSONAS_BLUEPRINT.route("/split_prospects", methods=["POST"])
@require_user
def post_split_prospects(client_sdr_id: int):
    source_archetype_id = get_request_parameter(
        "source_archetype_id", request, json=True, required=True
    )
    target_archetype_ids = get_request_parameter(
        "target_archetype_ids", request, json=True, required=True
    )

    success, msg = create_persona_split_request(
        client_sdr_id=client_sdr_id,
        source_archetype_id=source_archetype_id,
        destination_archetype_ids=target_archetype_ids,
    )
    if not success:
        return msg, 400

    return "OK", 200


@PERSONAS_BLUEPRINT.route("/recent_split_requests", methods=["GET"])
@require_user
def get_recent_split_requests_endpoint(client_sdr_id: int):
    source_archetype_id = get_request_parameter(
        "source_archetype_id", request, json=False, required=True
    )
    recent_requests = get_recent_split_requests(
        client_sdr_id=client_sdr_id, source_archetype_id=source_archetype_id
    )

    return jsonify({"recent_requests": recent_requests}), 200


@PERSONAS_BLUEPRINT.route("/split_request", methods=["GET"])
@require_user
def get_split_request(client_sdr_id: int):
    split_request_id = get_request_parameter(
        "split_request_id", request, json=False, required=True
    )

    details = get_split_request_details(split_request_id=split_request_id)

    return jsonify({"details": details}), 200
