from app import db

from flask import Blueprint, jsonify, request
from src.prospecting.models import ProspectStatus
from src.prospecting.services import (
    batch_mark_prospects_as_sent_outreach,
    create_prospect_from_linkedin_link,
    create_prospects_from_linkedin_link_list,
    prospect_exists_for_archetype,
    update_prospect_status,
    validate_prospect_json_payload,
    add_prospects_from_json_payload,
    toggle_ai_engagement,
    send_slack_reminder_for_prospect,
)
from src.client.models import ClientArchetype
from src.client.services import get_client_archetype
from src.utils.request_helpers import get_request_parameter
from src.prospecting.services import (
    batch_update_prospect_statuses,
    mark_prospect_reengagement,
)

from tqdm import tqdm
from src.prospecting.services import delete_prospect_by_id

from src.utils.random_string import generate_random_alphanumeric

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)


@PROSPECTING_BLUEPRINT.route("/", methods=["PATCH"])
def update_status():
    from model_import import ProspectStatus

    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    new_status = ProspectStatus[
        get_request_parameter("new_status", request, json=True, required=True)
    ]
    note = get_request_parameter("note", request, json=True, required=False)

    success = update_prospect_status(
        prospect_id=prospect_id, new_status=new_status, note=note
    )

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
    create_prospect_from_linkedin_link.delay(
        archetype_id=archetype_id, url=url, batch=batch
    )

    return "OK", 200


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


@PROSPECTING_BLUEPRINT.route("/send_slack_reminder", methods=["POST"])
def send_slack_reminder():
    """Sends a slack reminder to the SDR for a prospect when the SDR's attention is requried.
    This could occur as a result of a message with the SellScale AI is unable to respond to.

    Returns:
        status: 200 if successful, 400 if failed
    """
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    alert_reason = get_request_parameter(
        "alert_reason", request, json=True, required=True
    )

    success = send_slack_reminder_for_prospect(
        prospect_id=prospect_id, alert_reason=alert_reason
    )

    if success:
        return "OK", 200

    return "Failed to update", 400


@PROSPECTING_BLUEPRINT.route("/add_prospect_from_csv_payload", methods=["POST"])
def add_prospect_from_csv_payload():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    csv_payload = get_request_parameter(
        "csv_payload", request, json=True, required=True
    )

    validated, reason = validate_prospect_json_payload(payload=csv_payload)
    if not validated:
        return reason, 400

    success, couldnt_add = add_prospects_from_json_payload(
        client_id=client_id, archetype_id=archetype_id, payload=csv_payload
    )

    if success:
        return "OK", 200

    return "Error", 400


@PROSPECTING_BLUEPRINT.route("/delete_prospect", methods=["DELETE"])
def delete_prospect():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    success = delete_prospect_by_id(prospect_id=prospect_id)

    if success:
        return "OK", 200

    return "Failed to delete prospect", 400


@PROSPECTING_BLUEPRINT.route("/toggle_ai_engagement", methods=["POST"])
def post_toggle_ai_engagement():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    success = toggle_ai_engagement(prospect_id=prospect_id)

    if success:
        return "OK", 200

    return "Failed to toggle AI engagement", 400
