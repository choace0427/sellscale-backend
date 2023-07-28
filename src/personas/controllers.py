from src.authentication.decorators import require_user
from app import db

from flask import Blueprint, jsonify, request
from src.personas.services import (
    create_persona_split_request,
    get_recent_split_requests,
    get_split_request_details,
    get_unassignable_prospects_using_icp_heuristic,
    unassign_prospects,
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


@PERSONAS_BLUEPRINT.route("/prospects/unassign", methods=["GET"])
@require_user
def get_persona_unassign_prospects(client_sdr_id: int):
    """Returns a sample of 10 prospects from a persona, to be unassigned"""
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )

    _, prospect_dicts, count = get_unassignable_prospects_using_icp_heuristic(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id
    )

    return jsonify({"status": "success", "data": {"prospects": prospect_dicts, "total_count": count}}), 200


@PERSONAS_BLUEPRINT.route("/prospects/unassign", methods=["POST"])
@require_user
def post_persona_unassign_prospects(client_sdr_id: int):
    """Cleans prospects from a persona, moving them into the Unassigned tab"""
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    manual_unassign_list = get_request_parameter(
        "manual_unassign_list", request, json=True, required=False, parameter_type=list, default_value=[]
    )
    use_icp_heuristic = get_request_parameter(
        "use_icp_heuristic", request, json=True, required=False, parameter_type=bool, default_value=False
    )

    success = unassign_prospects.delay(
        client_sdr_id,
        client_archetype_id,
        use_icp_heuristic,
        manual_unassign_list,
    )
    if not success:
        return jsonify({"status": "error", "message": "Unable to unassign prospects"}), 400

    return jsonify({"status": "success", "data": {}}), 200


@PERSONAS_BLUEPRINT.route("/prospect_from_li_url", methods=["GET"])
@require_user
def get_prospect_from_li_url(client_sdr_id: int):
    """Gets a prospect from a LinkedIn URL"""
    li_url = get_request_parameter(
        "li_url", request, json=False, required=True, parameter_type=str
    )

    from src.prospecting.services import find_prospect_id_from_li_or_email
    
    prospect_id = find_prospect_id_from_li_or_email(client_sdr_id, li_url, None)

    return jsonify({"status": "success", "data": {
        "prospect_id": prospect_id
    }}), 200
