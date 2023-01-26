from app import db

from flask import Blueprint, jsonify, request
from src.prospecting.models import ProspectStatus
from src.prospecting.services import (
    batch_mark_prospects_as_sent_outreach,
    create_prospect_from_linkedin_link,
    create_prospects_from_linkedin_link_list,
    batch_mark_as_lead,
    update_prospect_status,
    validate_prospect_json_payload,
    add_prospects_from_json_payload,
    toggle_ai_engagement,
    send_slack_reminder_for_prospect,
    create_prospect_note,
    get_prospect_details,
    batch_update_prospect_statuses,
    mark_prospect_reengagement,
)
from src.prospecting.upload.services import ( 
    create_raw_csv_entry_from_json_payload,
    populate_prospect_uploads_from_json_payload,
    collect_and_run_celery_jobs_for_upload,
)
from src.utils.request_helpers import get_request_parameter

from tqdm import tqdm
from src.prospecting.services import delete_prospect_by_id

from src.utils.random_string import generate_random_alphanumeric

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)


@PROSPECTING_BLUEPRINT.route("/<prospect_id>", methods=["GET"])
def get_prospect_details_endpoint(prospect_id):
    prospect: dict = get_prospect_details(prospect_id)
    return jsonify(prospect), 200


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
    """ Adds prospect from CSV payload (given as JSON) from Retool

    First stores the entire csv in `prospect_uploads_raw_csv` table
    Then populates the `prospect_uploads` table
    Then runs the celery job to create prospects from the `prospect_uploads` table
    """
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    archetype_id = get_request_parameter("archetype_id", request, json=True, required=True)
    client_sdr_id = get_request_parameter("client_sdr_id", request, json=True, required=True)
    csv_payload = get_request_parameter("csv_payload", request, json=True, required=True)
    email_enabled = get_request_parameter("email_enabled", request, json=True, required=False)

    validated, reason = validate_prospect_json_payload(
        payload=csv_payload, email_enabled=email_enabled
    )
    if not validated:
        return reason, 400

    # Create prospect_uploads_csv_raw with a single entry
    raw_csv_entry_id = create_raw_csv_entry_from_json_payload(
        client_id=client_id, client_archetype_id=archetype_id, client_sdr_id=client_sdr_id, payload=csv_payload
    )
    if raw_csv_entry_id == -1:
        return "Duplicate CSVs are not allowed! Check that you're uploading a new CSV.", 400

    # Populate prospect_uploads table with multiple entries
    success = populate_prospect_uploads_from_json_payload(
        client_id=client_id, client_archetype_id=archetype_id, client_sdr_id=client_sdr_id, prospect_uploads_raw_csv_id=raw_csv_entry_id, payload=csv_payload
    )
    if not success:
        return "Failed to create prospect uploads", 400
    
    # Collect eligible prospect rows and create prospects
    success = collect_and_run_celery_jobs_for_upload(client_id=client_id, client_archetype_id=archetype_id, client_sdr_id=client_sdr_id)
    if not success:
        return "Something went wrong with collection and scheduling of celery jobs", 400

    return "Upload jobs successfully collected and scheduled.", 200


@PROSPECTING_BLUEPRINT.route("/retrigger_upload_job", methods=["POST"])
def retrigger_upload_prospect_job():
    """ Retriggers a prospect upload job that may have failed for some reason.

    Only runs on FAILED and NOT_STARTED jobs at the moment.

    Notable use case(s):
    - When iScraper fails
    """
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    archetype_id = get_request_parameter("archetype_id", request, json=True, required=True)
    client_sdr_id = get_request_parameter("client_sdr_id", request, json=True, required=True)

    success = collect_and_run_celery_jobs_for_upload(client_id=client_id, client_archetype_id=archetype_id, client_sdr_id=client_sdr_id)
    if not success:
        return "Something went wrong with collection and scheduling of celery jobs", 400

    return "Upload jobs successfully collected and scheduled.", 200


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


@PROSPECTING_BLUEPRINT.route("/add_note", methods=["POST"])
def post_add_note():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    note = get_request_parameter("note", request, json=True, required=True)

    data = create_prospect_note(prospect_id=prospect_id, note=note)
    return jsonify(data)


@PROSPECTING_BLUEPRINT.route("/batch_mark_as_lead", methods=["POST"])
def post_batch_mark_as_lead():
    payload = get_request_parameter("payload", request, json=True, required=True)
    success = batch_mark_as_lead(payload=payload)
    if success:
        return "OK", 200
    return "Failed to mark as lead", 400
