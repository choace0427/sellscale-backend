from typing import List

from src.prospecting.models import ExistingContact
from src.prospecting.services import (
    get_prospect_li_history,
    patch_prospect,
    prospect_removal_check_from_csv_payload,
)
from src.prospecting.models import ProspectNote
from src.prospecting.services import send_to_purgatory
from src.prospecting.nylas.services import (
    nylas_send_email,
    nylas_get_threads,
    nylas_update_threads,
    nylas_get_messages,
    nylas_update_messages,
)
from app import db

from flask import Blueprint, jsonify, request, Response
from src.prospecting.models import (
    Prospect,
    ProspectStatus,
    ProspectChannels,
    ProspectHiddenReason,
)
from datetime import datetime
from src.email_outbound.models import ProspectEmail
from src.email_outbound.models import ProspectEmailOutreachStatus
from src.prospecting.services import (
    mark_prospect_as_removed,
    search_prospects,
    get_prospects,
    batch_mark_prospects_as_sent_outreach,
    mark_prospects_as_queued_for_outreach,
    create_prospect_from_linkedin_link,
    create_prospects_from_linkedin_link_list,
    batch_mark_as_lead,
    update_prospect_status_linkedin,
    update_prospect_status_email,
    validate_prospect_json_payload,
    get_valid_channel_type_choices,
    toggle_ai_engagement,
    send_slack_reminder_for_prospect,
    get_prospects_for_icp,
    create_prospect_note,
    get_prospect_details,
    batch_update_prospect_statuses,
    mark_prospect_reengagement,
    get_prospect_generated_message,
    send_li_referral_outreach_connection,
    add_prospect_referral,
    add_existing_contact,
    get_existing_contacts,
    add_existing_contacts_to_persona,
    get_prospects_for_income_pipeline,
)
from src.prospecting.prospect_status_services import (
    get_valid_next_prospect_statuses,
    prospect_email_unsubscribe,
)
from src.prospecting.upload.services import (
    create_raw_csv_entry_from_json_payload,
    populate_prospect_uploads_from_json_payload,
    collect_and_run_celery_jobs_for_upload,
    run_and_assign_health_score,
)
from src.utils.request_helpers import get_request_parameter

from tqdm import tqdm
import time
from src.prospecting.services import delete_prospect_by_id

from src.utils.random_string import generate_random_alphanumeric
from src.authentication.decorators import require_user
from src.client.models import ClientArchetype, ClientSDR, Client
from src.utils.slack import send_slack_message, URL_MAP
from src.integrations.vessel import SalesEngagementIntegration
from src.email_outbound.email_store.hunter import (
    find_hunter_emails_for_prospects_under_archetype,
)
from src.prospecting.services import update_prospect_demo_date
from src.message_generation.services import add_generated_msg_queue

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)


@PROSPECTING_BLUEPRINT.route("/", methods=["GET"])
def get_prospect_by_uuids():
    """Get prospect by uuids"""
    client_uuid = get_request_parameter(
        "client_uuid", request, json=False, required=True
    )
    client_sdr_uuid = get_request_parameter(
        "client_sdr_uuid", request, json=False, required=True
    )
    prospect_uuid = get_request_parameter(
        "prospect_uuid", request, json=False, required=True
    )

    # Validate parameters
    if not client_uuid or not client_sdr_uuid or not prospect_uuid:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    # Get Client
    client: Client = Client.query.filter(Client.uuid == client_uuid).first()
    if not client:
        return jsonify({"status": "error", "message": "Client not found"}), 404

    # Get Client SDR
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.uuid == client_sdr_uuid
    ).first()
    if not client_sdr:
        return jsonify({"status": "error", "message": "Client SDR not found"}), 404
    elif client_sdr.client_id != client.id:
        return jsonify({"status": "error", "message": "Invalid parameters"}), 403

    # Get Prospect
    prospect: Prospect = Prospect.query.filter(Prospect.uuid == prospect_uuid).first()
    if not prospect:
        return jsonify({"status": "error", "message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr.id:
        return jsonify({"status": "error", "message": "Invalid parameters"}), 403

    return (
        jsonify(
            {
                "status": "Success",
                "data": {
                    "email": prospect.email,
                    "status": prospect.overall_status.value,
                },
            }
        ),
        200,
    )


@PROSPECTING_BLUEPRINT.route("/unsubscribe", methods=["POST"])
def post_prospect_unsubscribe():
    client_uuid = get_request_parameter(
        "client_uuid", request, json=True, required=True
    )
    client_sdr_uuid = get_request_parameter(
        "client_sdr_uuid", request, json=True, required=True
    )
    prospect_uuid = get_request_parameter(
        "prospect_uuid", request, json=True, required=True
    )

    # Validate parameters
    if not client_uuid or not client_sdr_uuid or not prospect_uuid:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    # Get Client
    client: Client = Client.query.filter(Client.uuid == client_uuid).first()
    if not client:
        return jsonify({"status": "error", "message": "Client not found"}), 404

    # Get Client SDR
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.uuid == client_sdr_uuid
    ).first()
    if not client_sdr:
        return jsonify({"status": "error", "message": "Client SDR not found"}), 404
    elif client_sdr.client_id != client.id:
        return jsonify({"status": "error", "message": "Invalid parameters"}), 403

    # Get Prospect
    prospect: Prospect = Prospect.query.filter(Prospect.uuid == prospect_uuid).first()
    if not prospect:
        return jsonify({"status": "error", "message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr.id:
        return jsonify({"status": "error", "message": "Invalid parameters"}), 403

    # Unsubscribe
    success = prospect_email_unsubscribe(prospect_id=prospect.id)
    if not success:
        return jsonify({"status": "error", "message": "Failed to unsubscribe"}), 400

    return jsonify({"status": "success", "data": None}), 200


@PROSPECTING_BLUEPRINT.route("/<prospect_id>", methods=["GET"])
@require_user
def get_prospect_details_endpoint(client_sdr_id: int, prospect_id: int):
    """Get prospect details"""
    prospect_details: dict = get_prospect_details(client_sdr_id, prospect_id)

    status_code = prospect_details.get("status_code")
    if status_code != 200:
        return jsonify({"message": prospect_details.get("message")}), status_code

    return (
        jsonify(
            {
                "message": "Success",
                "prospect_info": prospect_details.get("prospect_info"),
            }
        ),
        200,
    )


@PROSPECTING_BLUEPRINT.route("/<prospect_id>", methods=["PATCH"])
@require_user
def update_status(client_sdr_id: int, prospect_id: int):
    """Update prospect status or apply note"""
    # Get parameters
    override_status = (
        get_request_parameter(
            "override_status", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    quietly = (
        get_request_parameter(
            "quietly", request, json=True, required=False, parameter_type=bool
        )
        or False
    )

    channel_type = (
        get_request_parameter(
            "channel_type", request, json=True, required=True, parameter_type=str
        )
        or ProspectChannels.LINKEDIN.value
    )
    if channel_type == ProspectChannels.LINKEDIN.value:
        new_status = ProspectStatus[
            get_request_parameter(
                "new_status", request, json=True, required=True, parameter_type=str
            )
        ]
    elif channel_type == ProspectChannels.EMAIL.value:
        new_status = ProspectEmailOutreachStatus[
            get_request_parameter(
                "new_status", request, json=True, required=True, parameter_type=str
            )
        ]
    else:
        return jsonify({"message": "Invalid channel type"}), 400

    # Validate parameters
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Not authorized"}), 401

    # Update prospect status
    if channel_type == ProspectChannels.LINKEDIN.value:
        success = update_prospect_status_linkedin(
            prospect_id=prospect_id,
            new_status=new_status,
            manually_send_to_purgatory=False,
            override_status=override_status,
            quietly=quietly,
        )
        if (len(success) == 2 and success[0]) or (len(success) == 1 and success):
            return (
                jsonify(
                    {"message": "Successfully updated Prospect LinkedIn channel status"}
                ),
                200,
            )
        else:
            return jsonify({"message": "Failed to update: " + str(success[1])}), 400
    elif channel_type == ProspectChannels.EMAIL.value:
        success = update_prospect_status_email(
            prospect_id=prospect_id,
            new_status=new_status,
            override_status=override_status,
            quietly=quietly,
        )
        if success[0]:
            return (
                jsonify(
                    {"message": "Successfully updated Prospect Email channel status"}
                ),
                200,
            )
        else:
            return jsonify({"message": "Failed to update: " + success[1]}), 400


@PROSPECTING_BLUEPRINT.route("/<int:prospect_id>/entity", methods=["PATCH"])
@require_user
def patch_prospect_endpoint(client_sdr_id: int, prospect_id: int):
    """Patches a prospect"""
    title = get_request_parameter(
        "title", request, json=True, required=False, parameter_type=str
    )
    email = get_request_parameter(
        "email", request, json=True, required=False, parameter_type=str
    )
    linkedin_url = get_request_parameter(
        "linkedin_url", request, json=True, required=False, parameter_type=str
    )
    company_name = get_request_parameter(
        "company_name", request, json=True, required=False, parameter_type=str
    )
    company_website = get_request_parameter(
        "company_website", request, json=True, required=False, parameter_type=str
    )
    contract_size = get_request_parameter(
        "contract_size", request, json=True, required=False, parameter_type=int
    )

    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return jsonify({"status": "error", "message": "Prospect not found"}), 404
    if p.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Not authorized"}), 401

    success = patch_prospect(
        prospect_id=prospect_id,
        title=title,
        email=email,
        linkedin_url=linkedin_url,
        company_name=company_name,
        company_website=company_website,
        contract_size=contract_size,
    )
    if not success:
        return jsonify({"status": "error", "message": "Failed to update prospect"}), 400

    return jsonify({"status": "success", "data": None}), 200


@PROSPECTING_BLUEPRINT.route("<prospect_id>/get_valid_next_statuses", methods=["GET"])
@require_user
def get_valid_next_statuses_endpoint(client_sdr_id: int, prospect_id: int):
    try:
        channel_type = get_request_parameter(
            "channel_type", request, json=False, required=True, parameter_type=str
        )
    except Exception as e:
        return e.args[0], 400

    prospect_id = prospect_id
    prospect = Prospect.query.filter(Prospect.client_sdr_id == client_sdr_id).first()
    if not prospect:
        return "Prospect not found", 404
    elif prospect.client_sdr_id != client_sdr_id:
        return "Prospect does not belong to user", 403

    statuses = get_valid_next_prospect_statuses(
        prospect_id=prospect_id, channel_type=channel_type
    )

    return jsonify(statuses)


@PROSPECTING_BLUEPRINT.route("<prospect_id>/email/threads", methods=["GET"])
@require_user
def get_email_threads(client_sdr_id: int, prospect_id: int):
    """Gets email threads between SDR and prospect, stored in DB"""
    limit = get_request_parameter("limit", request, json=False, required=True)
    offset = get_request_parameter("offset", request, json=False, required=True)

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr.nylas_active:
        return jsonify({"message": "Nylas not connected"}), 400

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    threads = nylas_get_threads(client_sdr_id, prospect_id, int(limit), int(offset))

    return jsonify({"message": "Success", "data": threads}), 200


@PROSPECTING_BLUEPRINT.route("<prospect_id>/email/messages", methods=["GET"])
@require_user
def get_email_messages(client_sdr_id: int, prospect_id: int):
    """Gets email messages between SDR and prospect, stored in DB"""
    message_ids = get_request_parameter(
        "message_ids", request, json=False, required=False
    )
    thread_id = get_request_parameter("thread_id", request, json=False, required=False)
    if message_ids:
        message_ids = message_ids.split(",")

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr.nylas_active:
        return jsonify({"message": "Nylas not connected"}), 400

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    messages = nylas_get_messages(
        client_sdr_id, prospect_id, message_ids=message_ids, thread_id=thread_id
    )

    return jsonify({"message": "Success", "data": messages}), 200


@PROSPECTING_BLUEPRINT.route("<prospect_id>/email", methods=["POST"])
@require_user
def post_send_email(client_sdr_id: int, prospect_id: int):

    subject = get_request_parameter("subject", request, json=True, required=True)
    body = get_request_parameter("body", request, json=True, required=True)
    ai_generated = get_request_parameter(
        "ai_generated", request, json=True, required=False, parameter_type=bool
    )
    if ai_generated is None:
        ai_generated = False
    reply_to_message_id = get_request_parameter(
        "reply_to_message_id", request, json=True, required=False, parameter_type=str
    )

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    prospect_email_id = prospect.approved_prospect_email_id

    result = nylas_send_email(
        client_sdr_id, prospect_id, subject, body, reply_to_message_id, prospect_email_id
    )
    nylas_message_id = result.get("id")
    if isinstance(nylas_message_id, str) and ai_generated:
        add_generated_msg_queue(
            client_sdr_id=client_sdr_id, nylas_message_id=nylas_message_id
        )

    return jsonify({"message": "Success", "data": result}), 200


@PROSPECTING_BLUEPRINT.route("<prospect_id>/send_to_purgatory", methods=["POST"])
@require_user
def post_send_to_purgatory(client_sdr_id: int, prospect_id: int):

    days = get_request_parameter("days", request, json=False, required=True)

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    send_to_purgatory(prospect_id, int(days), ProspectHiddenReason.MANUAL)

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("<prospect_id>/email/<email_id>", methods=["GET"])
@require_user
def get_email(client_sdr_id: int, prospect_id: int, email_id: int):

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    if not prospect_email:
        return jsonify({"message": "No prospect email data found"}), 404

    try:
        sei = SalesEngagementIntegration(prospect.client_id)

        data = sei.get_email_by_id(email_id=email_id)
    except:
        data = {}

    return (
        jsonify(
            {"message": "Success", "data": data["email"] if data.get("email") else None}
        ),
        200,
    )


@PROSPECTING_BLUEPRINT.route(
    "/<prospect_id>/<outbound_type>/get_generated_message/", methods=["GET"]
)
# TODO: Needs some form of authentication
def get_generated_message_endpoint(prospect_id: int, outbound_type: str):
    """Get generated message"""
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404

    message = get_prospect_generated_message(
        prospect_id=prospect_id, outbound_type=outbound_type
    )

    return jsonify({"message": message})


@PROSPECTING_BLUEPRINT.route("/search", methods=["GET"])
def search_prospects_endpoint():
    """Search for prospects

    Parameters:
        - query (str): The search query
        - limit (int): The number of results to return
        - offset (int): The offset to start from

    Returns:
        A list of prospect matches in json format
    """
    query = get_request_parameter("query", request, json=False, required=True)
    client_id = get_request_parameter("client_id", request, json=False, required=True)
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=False, required=True
    )
    limit = get_request_parameter("limit", request, json=False, required=False) or 10
    offset = get_request_parameter("offset", request, json=False, required=False) or 0

    prospects: list[Prospect] = search_prospects(
        query, int(client_id), int(client_sdr_id), limit, offset
    )

    return jsonify([p.to_dict() for p in prospects]), 200


@PROSPECTING_BLUEPRINT.route("/get_prospects", methods=["POST"])
@require_user
def get_prospects_endpoint(client_sdr_id: int):
    """Gets prospects, paginated, for the SDR.

    Returns 20 prospects by default.

    Parameters:
        - query (str) (optional): A filter query
        - channel (str) (optional): The channel to filter by (ProspectChannels)
        - status (str) (optional): The status of the prospect (ProspectStatus)
        - persona_id (int) (optional): The id of the persona to filter by
        - limit (int) (optional): The number of results to return
        - offset (int) (optional): The offset to start from
        - ordering (str) (optional): The ordering of the results
        - bumped (str) (optional): The bumped count of the prospect
        - show_purgatory (bool | 'ALL') (optional): Whether to show prospects in purgatory
    """
    try:
        channel = (
            get_request_parameter(
                "channel", request, json=True, required=False, parameter_type=str
            )
            or ProspectChannels.LINKEDIN.value  # Default to LinkedIn for the time being
        )
        status = (
            get_request_parameter(
                "status", request, json=True, required=False, parameter_type=list
            )
            or None
        )
        query = (
            get_request_parameter(
                "query", request, json=True, required=False, parameter_type=str
            )
            or ""
        )
        persona_id = (
            get_request_parameter(
                "persona_id", request, json=True, required=False, parameter_type=int
            )
            or -1
        )
        limit = (
            get_request_parameter(
                "limit", request, json=True, required=False, parameter_type=int
            )
            or 20
        )
        offset = (
            get_request_parameter(
                "offset", request, json=True, required=False, parameter_type=int
            )
            or 0
        )
        ordering = (
            get_request_parameter(
                "ordering", request, json=True, required=False, parameter_type=list
            )
            or []
        )
        bumped = (
            get_request_parameter(
                "bumped", request, json=True, required=False, parameter_type=str
            )
            or "all"
        )
        show_purgatory = (
            get_request_parameter(
                "show_purgatory",
                request,
                json=True,
                required=False,
            )
            or False
        )
        shallow_data = (
            get_request_parameter(
                "shallow_data",
                request,
                json=True,
                required=False,
            )
            or False
        )
    except Exception as e:
        return e.args[0], 400

    # Validate the filters
    if len(ordering) > 0:
        for order in ordering:
            keys = order.keys()
            if len(keys) != 2 or keys != {"field", "direction"}:
                return jsonify({"message": "Invalid filters supplied to API"}), 400

    start_time = time.time()

    prospects_info: dict[int, list[Prospect]] = get_prospects(
        client_sdr_id,
        query,
        channel,
        status,
        persona_id,
        limit,
        offset,
        ordering,
        bumped,
        show_purgatory,
    )

    end_time = time.time()
    elapsed_time = end_time - start_time

    total_count = prospects_info.get("total_count")
    prospects = prospects_info.get("prospects")

    return (
        jsonify(
            {
                "message": "Success",
                "total_count": total_count,
                "prospects": [
                    (
                        p.to_dict(shallow_data=True)
                        if shallow_data
                        else p.to_dict(return_convo=True)
                    )
                    for p in prospects
                ],
                "elapsed_time": elapsed_time,
            }
        ),
        200,
    )


@PROSPECTING_BLUEPRINT.route("/from_link", methods=["POST"])
@require_user
def prospect_from_link(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    url = get_request_parameter("url", request, json=True, required=True)
    live = get_request_parameter("live", request, json=True, required=False) or False

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return jsonify({"status": "error", "message": "Invalid archetype id"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Not authorized"}), 401

    batch = generate_random_alphanumeric(32)
    prospect_id = None
    if not live:
        create_prospect_from_linkedin_link.apply_async(
            args=[archetype_id, url, batch],
            queue="prospecting",
            routing_key="prospecting",
            priority=1,
            link=run_and_assign_health_score.signature(
                args=[archetype_id],
                queue="prospecting",
                routing_key="prospecting",
                priority=3,
                immutable=True,
            ),
        )
    else:
        success, prospect_id = create_prospect_from_linkedin_link(
            archetype_id=archetype_id, url=url, batch=batch
        )
        if not success:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Failed to create prospect. Please check profile or check for duplicates.",
                    }
                ),
                400,
            )
        run_and_assign_health_score(archetype_id=archetype_id, live=True)

    return jsonify({"status": "success", "data": {"prospect_id": prospect_id}}), 200


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


# @PROSPECTING_BLUEPRINT.route("/batch_mark_sent", methods=["POST"])
# def batch_mark_sent():
#     updates = batch_mark_prospects_as_sent_outreach(
#         prospect_ids=get_request_parameter(
#             "prospect_ids", request, json=True, required=True
#         ),
#         client_sdr_id=get_request_parameter(
#             "client_sdr_id", request, json=True, required=True
#         ),
#     )
#     return jsonify({"updates": updates})


@PROSPECTING_BLUEPRINT.route("/batch_mark_queued", methods=["POST"])
def batch_mark_queued():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True, parameter_type=int
    )

    success, err = mark_prospects_as_queued_for_outreach(
        prospect_ids=prospect_ids, client_sdr_id=client_sdr_id
    )

    if success:
        return jsonify({"message": "Success"}), 200
    else:
        return jsonify({"message": "Failed to update", "error": err.get("error")}), 400


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
@require_user
def add_prospect_from_csv_payload(client_sdr_id: int):
    """Adds prospect from CSV payload (given as JSON) from Retool

    First stores the entire csv in `prospect_uploads_raw_csv` table
    Then populates the `prospect_uploads` table
    Then runs the celery job to create prospects from the `prospect_uploads` table
    """
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    csv_payload = get_request_parameter(
        "csv_payload", request, json=True, required=True, parameter_type=list
    )
    allow_duplicates = get_request_parameter(
        "allow_duplicates", request, json=True, required=False, parameter_type=bool
    )
    allow_duplicates = True if allow_duplicates is None else allow_duplicates

    if len(csv_payload) >= 3000:
        return "Too many rows in CSV", 400

    validated, reason = validate_prospect_json_payload(payload=csv_payload)
    if not validated:
        return reason, 400

    # Get client ID from client archetype ID.
    archetype = ClientArchetype.query.filter(
        ClientArchetype.id == archetype_id,
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).first()
    if not archetype:
        return "Archetype with given ID not found", 400

    # Check for duplicates is always enabled if client is not SellScale
    if archetype.client_id != 1:
        allow_duplicates = True

    # Create prospect_uploads_csv_raw with a single entry
    raw_csv_entry_id = create_raw_csv_entry_from_json_payload(
        client_id=archetype.client_id,
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        payload=csv_payload,
        allow_duplicates=allow_duplicates,
    )
    if raw_csv_entry_id == -1:
        return (
            "Duplicate CSVs are not allowed! Check that you're uploading a new CSV.",
            400,
        )

    # Populate prospect_uploads table with multiple entries
    success = populate_prospect_uploads_from_json_payload(
        client_id=archetype.client_id,
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        prospect_uploads_raw_csv_id=raw_csv_entry_id,
        payload=csv_payload,
        allow_duplicates=allow_duplicates,
    )
    if not success:
        return "Failed to create prospect uploads", 400

    # Collect eligible prospect rows and create prospects
    collect_and_run_celery_jobs_for_upload.apply_async(
        args=[archetype.client_id, archetype_id, client_sdr_id, allow_duplicates],
        queue="prospecting",
        routing_key="prospecting",
        priority=1,
    )

    client_sdr = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    client = Client.query.filter(Client.id == client_sdr.client_id).first()
    try:
        send_slack_message(
            message="{user} uploaded {X} prospects under the {persona} persona from {client_name}".format(
                user=client_sdr.name,
                X=len(csv_payload),
                persona=archetype.archetype,
                client_name=client.company,
            ),
            webhook_urls=[URL_MAP["operations-prospect-uploads"]],
        )
    except Exception as e:
        print("Failed to send slack notification: {}".format(e))

    return "Upload job scheduled.", 200


@PROSPECTING_BLUEPRINT.route("/retrigger_upload_job", methods=["POST"])
@require_user
def retrigger_upload_prospect_job(client_sdr_id: int):
    """Retriggers a prospect upload job that may have failed for some reason.

    Only runs on FAILED and NOT_STARTED jobs at the moment.

    Notable use case(s):
    - When iScraper fails
    """
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )

    client_sdr = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()

    collect_and_run_celery_jobs_for_upload.apply_async(
        args=[client_sdr.client_id, archetype_id, client_sdr_id],
        queue="prospecting",
        routing_key="prospecting",
        priority=1,
    )

    return (
        jsonify({"message": "Upload jobs successfully collected and scheduled."}),
        200,
    )


@PROSPECTING_BLUEPRINT.route("/delete_prospect", methods=["DELETE"])
def delete_prospect():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    success = delete_prospect_by_id(prospect_id=prospect_id)

    if success:
        return "OK", 200

    return "Failed to delete prospect", 400


@PROSPECTING_BLUEPRINT.route("/<prospect_id>/ai_engagement", methods=["PATCH"])
@require_user
def patch_toggle_ai_engagement(client_sdr_id: int, prospect_id: int):
    success = toggle_ai_engagement(client_sdr_id=client_sdr_id, prospect_id=prospect_id)

    if success:
        return jsonify({"status": "success"}), 200

    return (
        jsonify(
            {"status": "error", "message": "Failed to toggle AI engagement setting"}
        ),
        400,
    )


@PROSPECTING_BLUEPRINT.route("/add_note", methods=["POST"])
@require_user
def post_add_note(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    note = get_request_parameter(
        "note", request, json=True, required=True, parameter_type=str
    )

    # Check that prospect exists and belongs to user
    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if prospect is None:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    prospect_note_id = create_prospect_note(prospect_id=prospect_id, note=note)
    return jsonify({"message": "Success", "prospect_note_id": prospect_note_id}), 200


@PROSPECTING_BLUEPRINT.route("/note", methods=["GET"])
@require_user
def get_single_note(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True, parameter_type=int
    )

    # Check that prospect exists and belongs to user
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect is None:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    prospect_notes: List[ProspectNote] = ProspectNote.get_prospect_notes(prospect_id)
    if len(prospect_notes) == 0:
        # Make sure there's at least one note
        create_prospect_note(prospect_id=prospect_id, note="")
        prospect_notes: List[ProspectNote] = ProspectNote.get_prospect_notes(
            prospect_id
        )

    return jsonify({"message": "Success", "data": prospect_notes[-1].to_dict()}), 200


@PROSPECTING_BLUEPRINT.route("/note", methods=["PUT"])
@require_user
def update_single_note(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    note = get_request_parameter(
        "note", request, json=True, required=True, parameter_type=str
    )

    # Check that prospect exists and belongs to user
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect is None:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    prospect_notes: List[ProspectNote] = ProspectNote.get_prospect_notes(prospect_id)
    if len(prospect_notes) == 0:
        create_prospect_note(prospect_id=prospect_id, note=note)
    else:
        prospect_notes[-1].note = note
        db.session.commit()

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("/batch_mark_as_lead", methods=["POST"])
def post_batch_mark_as_lead():
    payload = get_request_parameter("payload", request, json=True, required=True)
    success = batch_mark_as_lead(payload=payload)
    if success:
        return "OK", 200
    return "Failed to mark as lead", 400


@PROSPECTING_BLUEPRINT.route("/get_valid_channel_types", methods=["GET"])
def get_valid_channel_types():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True
    )
    return jsonify({"choices": get_valid_channel_type_choices(prospect_id)})


@PROSPECTING_BLUEPRINT.route("/pull_emails", methods=["POST"])
@require_user
def pull_prospect_emails(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    success = find_hunter_emails_for_prospects_under_archetype.apply_async(
        args=[client_sdr_id, archetype_id]
    )
    if success:
        return jsonify({"message": "Success"}), 200
    return jsonify({"message": "Unable to fetch emails"}), 400


@PROSPECTING_BLUEPRINT.route("/get_credits", methods=["GET"])
@require_user
def get_credits(client_sdr_id: int):
    client_sdr = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    return jsonify({"email_fetching_credits": client_sdr.email_fetching_credits})


@PROSPECTING_BLUEPRINT.route("/remove_from_contact_list", methods=["POST"])
@require_user
def remove_from_contact_list(client_sdr_id: int):
    """
    Removes a prospect from the contact list.
    """
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True
    )
    success = mark_prospect_as_removed(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id
    )
    if success:
        return "OK", 200
    return "Failed to remove prospect from contact list", 400


@PROSPECTING_BLUEPRINT.route("/<prospect_id>/demo_date", methods=["POST"])
@require_user
def post_demo_date(client_sdr_id: int, prospect_id: int):
    demo_date = get_request_parameter("demo_date", request, json=True, required=True)
    send_reminder = get_request_parameter(
        "send_reminder",
        request,
        json=True,
        required=False,
        parameter_type=bool,
        default_value=False,
    )

    success = update_prospect_demo_date(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        demo_date=demo_date,
        send_reminder=send_reminder,
    )

    date = datetime.fromisoformat(demo_date[:-1])
    hidden_days = (date - datetime.now()).days
    if hidden_days > 0:
        send_to_purgatory(prospect_id, hidden_days, ProspectHiddenReason.DEMO_SCHEDULED)

    if success:
        return "OK", 200
    return "Failed to update demo date", 400


@PROSPECTING_BLUEPRINT.route("/<prospect_id>/demo_date", methods=["GET"])
@require_user
def get_demo_date(client_sdr_id: int, prospect_id: int):
    prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    return jsonify({"demo_date": prospect.demo_date}), 200


@PROSPECTING_BLUEPRINT.route("/<prospect_id>/li_history", methods=["GET"])
@require_user
def get_li_history(client_sdr_id: int, prospect_id: int):

    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect not found"}), 404

    history = get_prospect_li_history(prospect_id=prospect_id)

    return jsonify({"message": "Success", "data": history}), 200


@PROSPECTING_BLUEPRINT.route("/<prospect_id>/update", methods=["POST"])
@require_user
def post_update_prospect(client_sdr_id: int, prospect_id: int):
    """Update prospect details"""
    # This should really be PATCH at '/<prospect_id>' but that's used for something else

    email = get_request_parameter(
        "email", request, json=True, required=False, parameter_type=str
    )
    in_icp_sample = get_request_parameter(
        "in_icp_sample", request, json=True, required=False, parameter_type=bool
    )
    icp_fit_score_override = get_request_parameter(
        "icp_fit_score_override", request, json=True, required=False, parameter_type=int
    )
    contract_size = get_request_parameter(
        "contract_size", request, json=True, required=False, parameter_type=int
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect not found"}), 404

    if email is not None:
        prospect.email = email
    if in_icp_sample is not None:
        prospect.in_icp_sample = in_icp_sample
    if icp_fit_score_override is not None:
        prospect.icp_fit_score_override = icp_fit_score_override
    if contract_size is not None:
        prospect.contract_size = contract_size

    db.session.commit()

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route(
    "/<prospect_id>/send_outreach_connection", methods=["POST"]
)
@require_user
def post_send_outreach_connection(client_sdr_id: int, prospect_id: int):
    """Sends a li outreach connection request to a prospect"""

    message = get_request_parameter(
        "message", request, json=True, required=True, parameter_type=str
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect not found"}), 404

    success = send_li_referral_outreach_connection(prospect_id, message)

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("/<prospect_id>/add_referral", methods=["POST"])
@require_user
def post_prospect_add_referral(client_sdr_id: int, prospect_id: int):
    """Adds a prospect that this prospect referred us to"""

    referred_id = get_request_parameter(
        "referred_id", request, json=True, required=True, parameter_type=int
    )
    meta_data = get_request_parameter("metadata", request, json=True, required=False)

    prospect: Prospect = Prospect.query.get(prospect_id)
    referred: Prospect = Prospect.query.get(referred_id)
    if (
        not prospect
        or prospect.client_sdr_id != client_sdr_id
        or not referred
        or referred.client_sdr_id != client_sdr_id
    ):
        return jsonify({"message": "Prospect or referred prospect not found"}), 404

    success = add_prospect_referral(prospect_id, referred_id)  # , meta_data)

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("/icp_fit", methods=["GET"])
@require_user
def get_icp_fit_for_archetype(client_sdr_id: int):

    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True, parameter_type=str
    )
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Archetype not found"}), 404

    data = get_prospects_for_icp(archetype_id)

    return jsonify({"message": "Success", "data": data}), 200


@PROSPECTING_BLUEPRINT.route("/income_pipeline", methods=["GET"])
@require_user
def get_prospects_for_income_pipeline_endpoint(client_sdr_id: int):

    data = get_prospects_for_income_pipeline(client_sdr_id)

    return jsonify({"message": "Success", "data": data}), 200


@PROSPECTING_BLUEPRINT.route("/existing_contacts", methods=["POST"])
@require_user
def post_existing_contacts(client_sdr_id: int):

    existing_contacts = get_request_parameter(
        "data", request, json=True, required=True, parameter_type=list
    )
    connection_source = get_request_parameter(
        "connection_source", request, json=True, required=True, parameter_type=str
    )

    total_count = len(existing_contacts)
    added_count = 0
    for c in existing_contacts:
        contact_id = add_existing_contact(
            client_sdr_id=client_sdr_id,
            connection_source=connection_source,
            full_name=c.get("full_name", ""),
            first_name=c.get("first_name", None),
            last_name=c.get("last_name", None),
            title=c.get("title", None),
            bio=c.get("bio", None),
            linkedin_url=c.get("linkedin_url", None),
            instagram_url=c.get("instagram_url", None),
            facebook_url=c.get("facebook_url", None),
            twitter_url=c.get("twitter_url", None),
            email=c.get("email", None),
            phone=c.get("phone", None),
            address=c.get("address", None),
            li_public_id=c.get("li_public_id", None),
            li_urn_id=c.get("li_urn_id", None),
            img_url=c.get("img_url", None),
            img_expire=c.get("img_expire", None),
            industry=c.get("industry", None),
            company_name=c.get("company_name", None),
            company_id=c.get("company_id", None),
            linkedin_followers=c.get("linkedin_followers", None),
            instagram_followers=c.get("instagram_followers", None),
            facebook_followers=c.get("facebook_followers", None),
            twitter_followers=c.get("twitter_followers", None),
            notes=c.get("notes", None),
        )
        if contact_id:
            added_count += 1

    return (
        jsonify(
            {
                "message": "Success",
                "data": {"total_count": total_count, "added_count": added_count},
            }
        ),
        200,
    )


@PROSPECTING_BLUEPRINT.route("/existing_contacts", methods=["GET"])
@require_user
def get_existing_contacts_endpoint(client_sdr_id: int):

    limit = get_request_parameter(
        "limit",
        request,
        json=False,
        required=False,
        parameter_type=int,
        default_value=20,
    )
    offset = get_request_parameter(
        "offset",
        request,
        json=False,
        required=False,
        parameter_type=int,
        default_value=0,
    )
    search = get_request_parameter(
        "search",
        request,
        json=False,
        required=False,
        parameter_type=str,
        default_value="",
    )

    existing_contacts, total_rows = get_existing_contacts(
        client_sdr_id, limit, offset, search
    )

    return (
        jsonify(
            {
                "message": "Success",
                "data": {
                    "total_rows": total_rows,
                    "existing_contacts": existing_contacts,
                },
            }
        ),
        200,
    )


@PROSPECTING_BLUEPRINT.route("/existing_contacts/add_to_persona", methods=["POST"])
@require_user
def post_add_existing_contacts_to_persona(client_sdr_id: int):

    persona_id = get_request_parameter(
        "persona_id", request, json=True, required=True, parameter_type=int
    )
    contact_ids = get_request_parameter(
        "contact_ids", request, json=True, required=True, parameter_type=list
    )

    client_archetype: ClientArchetype = ClientArchetype.query.get(persona_id)
    if not client_archetype or client_archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Persona not found"}), 404

    added_count = add_existing_contacts_to_persona(persona_id, contact_ids)

    return jsonify({"message": "Success", "data": {"added_count": added_count}}), 200


@PROSPECTING_BLUEPRINT.route("/prospect_removal_check", methods=["POST"])
@require_user
def post_prospect_removal_check(client_sdr_id: int):
    parsed_csvs = get_request_parameter(
        "parsed_csvs", request, json=True, required=True
    )
    bulk_remove = get_request_parameter(
        "bulk_remove", request, json=True, required=False, parameter_type=bool
    )
    parsed_csv = parsed_csvs[0]

    return (
        jsonify(
            {
                "data": prospect_removal_check_from_csv_payload(
                    parsed_csv, client_sdr_id, bulk_remove
                )
            }
        ),
        200,
    )
