from typing import List

from typing import Optional

import requests
from src.automation.orchestrator import add_process_for_future
from src.contacts.models import SavedApolloQuery
from src.daily_notifications.services import get_engagement_feed_items_for_prospect
from src.email_outbound.email_store.services import find_emails_for_archetype
from src.prospecting.champions.services import (
    get_champion_detection_changes,
    get_champion_detection_stats,
    mark_prospects_as_champion,
    refresh_job_data_for_all_champions,
)
from src.prospecting.services import move_all_revival_prospects_back_to_previous_status, prospect_exists_for_client, \
    get_prospect_duplicate_details, get_duplicate_prospects_from_csv_payload
from src.prospecting.models import ExistingContact, ProspectUploadSource
from src.segment.models import Segment
from src.segment.services import (
    get_base_segment_for_archetype,
    merge_segment_filters,
)
from src.prospecting.services import (
    add_prospect,
    add_prospects_from_saved_apollo_query_id,
    bulk_mark_not_qualified,
    create_prospect_from_linkedin_link,
    get_linkedin_slug_from_url,
    get_prospect_email_history,
    get_prospect_li_history,
    get_prospect_overall_history,
    get_prospects_for_icp_table,
    global_prospected_contacts,
    inbox_restructure_fetch_prospects,
    move_prospect_to_persona,
    patch_prospect,
    prospect_removal_check_from_csv_payload,
    send_attempting_reschedule_notification,
    snooze_prospect_email,
    fetch_company_details,
    add_prospect_from_apollo,
)
from src.prospecting.models import ProspectNote
from src.prospecting.services import send_to_purgatory
from src.prospecting.nylas.services import (
    nylas_send_email,
    nylas_get_threads,
    nylas_get_messages,
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
    mark_prospects_as_queued_for_outreach,
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
    get_li_message_from_contents,
    add_prospect_message_feedback,
    extract_colloquialized_company_name,
    extract_colloquialized_prospect_title,
)
from src.prospecting.prospect_status_services import (
    get_valid_next_prospect_statuses,
    prospect_email_unsubscribe,
)
from src.prospecting.upload.services import (
    create_prospect_upload_history,
    create_raw_csv_entry_from_json_payload,
    upsert_and_run_apollo_upload_for_sdr,
    get_apollo_scraper_jobs,
    populate_prospect_uploads_from_json_payload,
    collect_and_run_celery_jobs_for_upload,
    update_apollo_scraper_job,
)
from src.slack.models import SlackNotificationType
from src.slack.notifications.email_multichanneled import EmailMultichanneledNotification
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)
from src.utils.abstract.attr_utils import deep_get
from src.utils.datetime.dateparse_utils import convert_string_to_datetime_or_none
from src.utils.email.html_cleaning import clean_html
from src.utils.request_helpers import get_request_parameter

from tqdm import tqdm
import time
from src.prospecting.services import delete_prospect_by_id

from src.utils.random_string import generate_random_alphanumeric
from src.authentication.decorators import require_user
from src.client.models import ClientArchetype, ClientSDR, Client
from src.utils.slack import send_slack_message, URL_MAP
from src.email_outbound.email_store.hunter import (
    find_hunter_emails_for_prospects_under_archetype,
)
from src.prospecting.services import update_prospect_demo_date
from src.message_generation.services import add_generated_msg_queue
from src.prospecting.prospect_email.services import (
    remove_email_out_of_office_status,
    check_and_remove_out_of_office_statuses,
)


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


@PROSPECTING_BLUEPRINT.route("/get-phone-number/<prospect_id>", methods=["GET"])
@require_user
def get_prospect_phone_number(client_sdr_id: int, prospect_id: int):
    prospect = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.id == prospect_id,
        ).first()

    if not prospect:
        return jsonify({"message": "This prospect does not belong to you."}), 400

    first_name = prospect.first_name
    last_name = prospect.last_name
    company = prospect.company

    response = requests.post("https://api.apollo.io/v1/people/match", json={
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": company,
        "reveal_phone_number": True,
        "webhook_url": f"https://sellscale-api-prod.onrender.com/webhooks/prospect/find-phone-number/{client_sdr_id}/{prospect_id}"
    })

    response_data = response.json()

    if response_data and response_data.get("contact") and response_data.get("contact").get("phone_numbers"):
        phone_numbers = response_data.get("contact").get("phone_numbers")
    else:
        return jsonify({"message": "We are fetching the number in the background. It might take a while", "fetching": True}), 200

    for phone_number in phone_numbers:
        if phone_number["type"] == "mobile":
            prospect.phone_number = phone_number["sanitized_number"]
            prospect.reveal_phone_number = True

            db.session.add(prospect)
            db.session.commit()

            return jsonify({"message": "Successfully fetched the number.", "fetching": False}), 200

    return jsonify({"message": "We cannot fetch a relevant number", "fetching": False}), 400





@PROSPECTING_BLUEPRINT.route("/<prospect_id>/shallow", methods=["GET"])
@require_user
def get_shallow_prospect(client_sdr_id: int, prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)

    return (
        jsonify({"message": "Success", "data": prospect.to_dict(shallow_data=True)}),
        200,
    )


@PROSPECTING_BLUEPRINT.route(
    "/<prospect_id>/send_attempting_reschedule_notification", methods=["POST"]
)
@require_user
def send_attempting_reschedule_notification_endpoint(
    client_sdr_id: int, prospect_id: int
):
    """Send attempting reschedule notification"""
    success = send_attempting_reschedule_notification(client_sdr_id, prospect_id)

    if success:
        return jsonify({"message": "Success"}), 200
    return jsonify({"message": "Failed to update"}), 400


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

    disqualification_reason = get_request_parameter(
        "disqualification_reason", request, json=True, required=False
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
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    is_admin = client_sdr.role == "ADMIN"
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif (
        prospect.client_sdr_id != client_sdr_id and not (
            client_sdr.client_id == prospect.client_id and is_admin
        )
    ):
        return jsonify({"message": "Not authorized"}), 401

    # Update prospect status
    if channel_type == ProspectChannels.LINKEDIN.value:
        success = update_prospect_status_linkedin(
            prospect_id=prospect_id,
            new_status=new_status,
            manually_send_to_purgatory=False,
            override_status=override_status,
            quietly=quietly,
            disqualification_reason=disqualification_reason,
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
            disqualification_reason=disqualification_reason,
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
    meta_data = get_request_parameter(
        "meta_data", request, json=True, required=False, parameter_type=dict
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
        meta_data=meta_data,
    )
    if not success:
        return jsonify({"status": "error", "message": "Failed to update prospect"}), 400

    return jsonify({"status": "success", "data": None}), 200


@PROSPECTING_BLUEPRINT.route("/<int:prospect_id>/demo_set", methods=["PATCH"])
@require_user
def patch_prospect_demo_set_endpoint(client_sdr_id: int, prospect_id: int):
    type = get_request_parameter(
        "type", request, json=True, required=False, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, parameter_type=str
    )

    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return jsonify({"status": "error", "message": "Prospect not found"}), 404
    if p.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Not authorized"}), 401

    success = patch_prospect(
        prospect_id=prospect_id,
        meta_data=(
            {
                **p.meta_data,
                "demo_set": {"type": type, "description": description},
            }
            if p.meta_data
            else {"demo_set": {"type": type, "description": description}}
        ),
    )

    if not success:
        return jsonify({"status": "error", "message": "Failed to update prospect"}), 400

    if type == "HANDOFF":
        send_slack_message(
            message="",
            webhook_urls=[client.pipeline_notifications_webhook_url],
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "{prospect_name} was handed off internally!! 🎉".format(
                            prospect_name=p.full_name
                        ),
                        "emoji": True,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "🧳 Title: "
                            + str(p.title)
                            + " @ "
                            + str(p.company)[0:20]
                            + ("..." if len(p.company) > 20 else ""),
                            "emoji": True,
                        },
                        {
                            "type": "plain_text",
                            "text": "📌 SDR: " + sdr.name,
                            "emoji": True,
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Handoff Details: {details}".format(
                            details=description
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": " ",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Prospect in Sight",
                            "emoji": True,
                        },
                        "value": "click_me_123",
                        "url": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                            auth_token=sdr.auth_token,
                            prospect_id=p.id,
                        ),
                        "action_id": "button-action",
                    },
                },
            ],
        )

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
    ai_generated = (
        get_request_parameter(
            "ai_generated", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    reply_to_message_id = get_request_parameter(
        "reply_to_message_id", request, json=True, required=False, parameter_type=str
    )
    is_multichannel_action = (
        get_request_parameter(
            "is_multichannel_action",
            request,
            json=True,
            required=False,
            parameter_type=bool,
        )
        or False
    )
    bcc = get_request_parameter("bcc", request, json=True, required=False)
    cc = get_request_parameter("cc", request, json=True, required=False)

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    prospect_email_id = prospect.approved_prospect_email_id

    result = nylas_send_email(
        client_sdr_id,
        prospect_id,
        subject,
        body,
        reply_to_message_id,
        prospect_email_id,
        bcc=bcc,
        cc=cc,
    )
    nylas_message_id = result.get("id")
    if isinstance(nylas_message_id, str) and ai_generated:
        add_generated_msg_queue(
            client_sdr_id=client_sdr_id, nylas_message_id=nylas_message_id
        )

    # If this is a multichannel action (i.e. email sent from a LinkedIn message), then send a Slack notification
    if is_multichannel_action:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)
        webhook_urls = [URL_MAP["eng-sandbox"]]
        from_email = result.get("from", [{"email": "Unknown"}])[0].get("email")
        prettier_body = clean_html(body)
        prettier_body = prettier_body.replace("\n", "\n>")
        if client.pipeline_notifications_webhook_url:
            webhook_urls.append(client.pipeline_notifications_webhook_url)

        # Send the notification
        success = create_and_send_slack_notification_class_message(
            notification_type=SlackNotificationType.EMAIL_MULTICHANNELED,
            arguments={
                "client_sdr_id": client_sdr_id,
                "prospect_id": prospect_id,
                "from_email": from_email,
                "email_sent_subject": subject,
                "email_sent_body": prettier_body,
            },
        )

        # multichannel_notification = EmailMultichanneledNotification(
        #     client_sdr_id=client_sdr.id,
        #     prospect_id=prospect.id,
        #     from_email=from_email,
        #     email_sent_subject=subject,
        #     email_sent_body=prettier_body,
        # )
        # multichannel_notification.send_notification(preview_mode=False)

    return jsonify({"message": "Success", "data": result}), 200


@PROSPECTING_BLUEPRINT.route("<prospect_id>/email/snooze", methods=["POST"])
@require_user
def post_snooze_email(client_sdr_id: int, prospect_id: int):
    num_days = get_request_parameter(
        "num_days", request, json=True, required=False, parameter_type=int
    )
    specific_time = get_request_parameter(
        "specific_time", request, json=True, required=False, parameter_type=str
    )
    if specific_time:
        specific_time = convert_string_to_datetime_or_none(content=specific_time)

    success = snooze_prospect_email(
        prospect_id=prospect_id,
        num_days=num_days,
        specific_time=specific_time,
    )
    if not success:
        return jsonify({"message": "Failed to snooze"}), 400

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("<prospect_id>/send_to_purgatory", methods=["POST"])
@require_user
def post_send_to_purgatory(client_sdr_id: int, prospect_id: int):
    days = get_request_parameter("days", request, json=False, required=True)

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    send_to_purgatory(
        prospect_id, int(days), ProspectHiddenReason.MANUAL, send_notification=True
    )

    return jsonify({"message": "Success"}), 200


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
        prospect_id = (
            get_request_parameter(
                "prospect_id",
                request,
                json=True,
                required=False,
            )
            or None
        )
        icp_fit_score = (
            get_request_parameter(
                "icp_fit_score",
                request,
                json=True,
                required=False,
            )
            or None
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
        client_sdr_id=client_sdr_id,
        query=query,
        channel=channel,
        status=status,
        persona_id=persona_id,
        limit=limit,
        offset=offset,
        ordering=ordering,
        bumped=bumped,
        show_purgatory=show_purgatory,
        prospect_id=prospect_id,
        icp_fit_score=icp_fit_score,
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


@PROSPECTING_BLUEPRINT.route("/get_prospect_for_icp", methods=["POST"])
@require_user
def get_prospects_for_icp(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    get_sample = get_request_parameter("get_sample", request, json=True, required=False)
    invited_on_linkedin = get_request_parameter(
        "invited_on_linkedin", request, json=True, required=False
    )

    prospects = get_prospects_for_icp_table(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        get_sample=get_sample,
        invited_on_linkedin=invited_on_linkedin,
    )

    return jsonify({"message": "Success", "data": {"prospects": prospects}}), 200


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

@PROSPECTING_BLUEPRINT.route("/add_from_apollo_query_id", methods=["POST"])
@require_user
def add_prospect_from_apollo_query_id(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=False, parameter_type=int
    )
    saved_apollo_query_id = get_request_parameter(
        "saved_apollo_query_id", request, json=True, required=True, parameter_type=int
    )
    segment_id = get_request_parameter(
        "segment_id", request, json=True, required=False, parameter_type=int
    )
    num_contacts = get_request_parameter(
        "num_contacts", request, json=True, required=False, parameter_type=int
    )

    if client_sdr_id not in (34, 221):
        return "OK (non-SellScale user)", 200

    success = add_prospects_from_saved_apollo_query_id(
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        saved_apollo_query_id=saved_apollo_query_id,
        allow_duplicates=False,
        segment_id=segment_id,
        num_contacts=num_contacts,
    )

    if success:
        return "OK", 200

    return "Failed to create prospect", 400


@PROSPECTING_BLUEPRINT.route("/check_duplicate_prospects_from_csv_payload", methods=["POST"])
@require_user
def check_duplicate_prospects_from_csv_payload(client_sdr_id: int):
    csv_payload = get_request_parameter(
        "csv_payload", request, json=True, required=True, parameter_type=list
    )

    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=False, parameter_type=int
    )

    return get_duplicate_prospects_from_csv_payload(client_sdr_id=client_sdr_id,
                                                    csv_payload=csv_payload, archetype_id=archetype_id)


@PROSPECTING_BLUEPRINT.route("/add_prospect_from_csv_payload", methods=["POST"])
@require_user
def post_add_prospect_from_csv_payload(client_sdr_id: int):
    """Adds prospect from CSV payload (given as JSON)

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
    segment_id = get_request_parameter(
        "segment_id", request, json=True, required=False, parameter_type=int
    )
    segment_filters = get_request_parameter(
        "segment_filters", request, json=True, required=False, parameter_type=dict
    )
    source = get_request_parameter(
        "source", request, json=True, required=False, parameter_type=str
    )
    allow_duplicates = True if allow_duplicates is None else allow_duplicates

    # Update segment filters
    if segment_id and segment_filters:
        merge_segment_filters(segment_id=segment_id, segment_filters=segment_filters)

    if source == "CSV":
        source = ProspectUploadSource.CSV
    elif source == "CONTACT_DATABASE":
        source = ProspectUploadSource.CONTACT_DATABASE
    else:
        source = ProspectUploadSource.CSV

    return add_prospect_from_csv_payload(
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        csv_payload=csv_payload,
        allow_duplicates=allow_duplicates,
        source=source,
        segment_id=segment_id,
    )

def add_prospects_from_saved_apollo_query_id(
    client_sdr_id: int,
    saved_apollo_query_id: int,
    archetype_id: Optional[int] = None,
    allow_duplicates: bool = False,
    segment_id: Optional[int] = None,
    num_contacts: int = 100
):
    from src.contacts.services import apollo_get_contacts_for_page

    source = ProspectUploadSource.CONTACT_DATABASE

    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.filter(
        SavedApolloQuery.id == saved_apollo_query_id
    ).first()
    if not saved_apollo_query:
        return "Saved Apollo Query not found", 400
        
    saved_apollo_query_client_sdr_id =saved_apollo_query.client_sdr_id
    saved_apollo_query_client_sdr = ClientSDR.query.get(saved_apollo_query_client_sdr_id)
    current_client_sdr = ClientSDR.query.get(client_sdr_id)
    if current_client_sdr.client_id != saved_apollo_query_client_sdr.client_id:
        return "Client SDR mismatch", 400
    
    if archetype_id:
        client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    else:
        unassigned_client_archetype = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == client_sdr_id,
            ClientArchetype.is_unassigned_contact_archetype == True
        ).first()
        archetype_id = unassigned_client_archetype.id
        client_archetype = unassigned_client_archetype
    
    if client_archetype and client_archetype.client_sdr_id != client_sdr_id:
        return "Client Archetype does not belong to user", 400
    
    segment: Segment = Segment.query.get(segment_id)
    if segment and segment.client_sdr_id != client_sdr_id:
        return "Segment does not belong to user", 400
    
    payload = saved_apollo_query.data
    num_pages = (num_contacts // 100) or 1
    all_contacts = []
    for page in range(1, num_pages + 1):
        print("Processesing page: ", page)
        response, data, saved_query_id = apollo_get_contacts_for_page(
            client_sdr_id=client_sdr_id,
            page=page,
            person_titles=payload.get("person_titles", []),
            person_not_titles=payload.get("person_not_titles", []),
            q_person_title=payload.get("q_person_title", ""),
            q_person_name=payload.get("q_person_name", ""),
            organization_industry_tag_ids=payload.get("organization_industry_tag_ids", []),
            organization_num_employees_ranges=payload.get(
                "organization_num_employees_ranges", []
            ),
            person_locations=payload.get("person_locations", []),
            organization_ids=payload.get("organization_ids", None),
            revenue_range=payload.get("revenue_range", {"min": None, "max": None}),
            organization_latest_funding_stage_cd=payload.get(
                "organization_latest_funding_stage_cd", []
            ),
            currently_using_any_of_technology_uids=payload.get(
                "currently_using_any_of_technology_uids", []
            ),
            event_categories=payload.get("event_categories", None),
            published_at_date_range=payload.get("published_at_date_range", None),
            person_seniorities=payload.get("person_seniorities", None),
            q_organization_search_list_id=payload.get(
                "q_organization_search_list_id", None
            ),
            organization_department_or_subdepartment_counts=payload.get(
                "organization_department_or_subdepartment_counts", None
            ),
            is_prefilter=payload.get("is_prefilter", False),
            q_organization_keyword_tags=payload.get("q_organization_keyword_tags", None),
        )

        # get the contacts and people
        contacts = response["contacts"]
        people = response["people"]
        new_contacts = contacts + people
        all_contacts = all_contacts + new_contacts

        # (at the top) create a Prospect Upload History entry
        # create `prospect_uploads` entries for each contact (in bulk using SQLAlchemy bulk insert)

        for contact in new_contacts:
            add_prospect_from_apollo.delay(
                current_client_sdr.client_id,
                archetype_id,
                client_sdr_id,
                contact,
                segment_id,
                # include propsect_uploads.id in this call
                    # within the call, update prospect_uploads status to SUCCESS if successful and update prospect_upload_history's processed counts

            )
            
    print(len(all_contacts))
    return True


def add_prospect_from_csv_payload(
    client_sdr_id: int,
    archetype_id: int,
    csv_payload: list,
    allow_duplicates: bool,
    source: ProspectUploadSource,
    segment_id: Optional[int] = None,
):
    if len(csv_payload) >= 5000:
        return (
            "Too many rows in CSV. The max row limit is 5,000. Your CSV has {} rows.".format(
                len(csv_payload)
            ),
            400,
        )

    validated, reason = validate_prospect_json_payload(payload=csv_payload)
    if not validated:
        return reason, 400

    # Get client ID from client archetype ID.
    archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.id == archetype_id,
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).first()
    if not archetype:
        return "Archetype with given ID not found", 400

    # Check for duplicates is always enabled if client is not SellScale
    if archetype.client_id != 1:
        allow_duplicates = True

    # Get the segment_id
    segment_id = segment_id or get_base_segment_for_archetype(archetype_id=archetype_id)

    # Create prospect_uploads_csv_raw with a single entry
    raw_csv_entry_id = create_raw_csv_entry_from_json_payload(
        client_id=archetype.client_id,
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        payload=csv_payload,
        allow_duplicates=allow_duplicates,
    )
    prospect_upload_history_id = create_prospect_upload_history(
        client_id=archetype.client_id,
        client_sdr_id=client_sdr_id,
        upload_source=source,
        raw_data=csv_payload,
        client_archetype_id=archetype_id,
        client_segment_id=segment_id,
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
        prospect_upload_history_id=prospect_upload_history_id,
        payload=csv_payload,
        source=source,
        allow_duplicates=allow_duplicates,
    )
    if not success:
        return "Failed to create prospect uploads", 400

    # Collect eligible prospect rows and create prospects
    collect_and_run_celery_jobs_for_upload.apply_async(
        args=[
            archetype.client_id,
            archetype_id,
            client_sdr_id,
            allow_duplicates,
        ],
        queue="prospecting",
        routing_key="prospecting",
        priority=1,
    )

    # Schedule a job to check on the Prospect Upload History
    add_process_for_future(
        type="refresh_prospect_upload_history",
        args={"prospect_upload_history_id": prospect_upload_history_id, "retry": True},
        minutes=1,  # 1 minute from now
    )

    # extract 3 Linkedin URLs from the payload
    linkedin_urls = []
    for row in csv_payload:
        if "linkedin_url" in row:
            linkedin_urls.append(row["linkedin_url"])
            if len(linkedin_urls) == 1:
                break
    for url in linkedin_urls:
        create_prospect_from_linkedin_link(
            archetype_id=archetype_id, url=url, segment_id=segment_id
        )

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

    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()

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

    success = find_emails_for_archetype.delay(archetype_id=archetype_id)
    # success = find_hunter_emails_for_prospects_under_archetype.apply_async(
    #     args=[client_sdr_id, archetype_id]
    # )
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
        client_sdr_id=client_sdr_id, prospect_id=prospect_id, manual=True
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
        #admin can see all prospects under a client
        client_sdr = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first() 
        if not (client_sdr.role == 'ADMIN' and prospect.client_id == client_sdr.client_id):
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


@PROSPECTING_BLUEPRINT.route("/<prospect_id>/history", methods=["GET"])
@require_user
def get_history(client_sdr_id: int, prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if not prospect or prospect.client_id != client_sdr.client_id:
        return jsonify({"message": "Prospect not found"}), 404

    li_history = get_prospect_li_history(prospect_id=prospect_id)
    email_history = get_prospect_email_history(prospect_id=prospect_id)
    engagements = get_engagement_feed_items_for_prospect(prospect_id=prospect_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": {
                    "linkedin": li_history,
                    "email": email_history,
                    "engagements": engagements,
                },
            }
        ),
        200,
    )


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


@PROSPECTING_BLUEPRINT.route(
    "<int:prospect_id>/determine_li_msg_from_content/", methods=["POST"]
)
@require_user
def post_determine_li_msg_from_content(client_sdr_id: int, prospect_id: int):
    content = get_request_parameter(
        "content", request, json=True, required=True, parameter_type=str
    )

    li_msg_id = get_li_message_from_contents(client_sdr_id, prospect_id, content)

    return jsonify({"message": "Success", "data": li_msg_id}), 200


@PROSPECTING_BLUEPRINT.route("<int:prospect_id>/li_msgs/", methods=["GET"])
@require_user
def get_li_msgs_for_prospect(client_sdr_id: int, prospect_id: int):
    from model_import import LinkedinConversationEntry

    convo: List[
        LinkedinConversationEntry
    ] = LinkedinConversationEntry.li_conversation_thread_by_prospect_id(prospect_id)

    return jsonify({"message": "Success", "data": [c.to_dict() for c in convo]}), 200


@PROSPECTING_BLUEPRINT.route("<int:prospect_id>/msg_feedback/", methods=["POST"])
@require_user
def post_add_msg_feedback(client_sdr_id: int, prospect_id: int):
    li_msg_id = (
        get_request_parameter(
            "li_msg_id", request, json=True, required=False, parameter_type=int
        )
        or None
    )
    email_msg_id = (
        get_request_parameter(
            "email_msg_id", request, json=True, required=False, parameter_type=int
        )
        or None
    )
    rating = get_request_parameter(
        "rating", request, json=True, required=True, parameter_type=int
    )
    feedback = get_request_parameter(
        "feedback", request, json=True, required=True, parameter_type=str
    )

    feedback_id = add_prospect_message_feedback(
        client_sdr_id, prospect_id, li_msg_id, email_msg_id, rating, feedback
    )

    return jsonify({"message": "Success", "data": feedback_id}), 200


@PROSPECTING_BLUEPRINT.route("/global_contacts", methods=["GET"])
@require_user
def get_global_contacts(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()
    if not client_sdr:
        return jsonify({"message": "Client SDR not found"}), 404

    client_id: int = client_sdr.client_id
    contacts = global_prospected_contacts(
        client_id=client_id,
    )

    return jsonify({"message": "Success", "data": contacts}), 200


@PROSPECTING_BLUEPRINT.route("/global_contacts/move_to_persona", methods=["POST"])
@require_user
def post_move_global_contacts_to_persona(client_sdr_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )
    new_archetype_id = get_request_parameter(
        "new_archetype_id", request, json=True, required=True, parameter_type=int
    )

    success = move_prospect_to_persona(
        client_sdr_id=client_sdr_id,
        prospect_ids=prospect_ids,
        new_archetype_id=new_archetype_id,
    )

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("/global_contacts/remove", methods=["POST"])
@require_user
def post_remove_global_contacts(client_sdr_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()

    client_id: int = client_sdr.client_id

    success = bulk_mark_not_qualified(
        client_id=client_id,
        prospect_ids=prospect_ids,
    )

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("/inbox_restructure_prospects", methods=["GET"])
@require_user
def get_inbox_restructure_prospects(client_sdr_id: int):
    results = inbox_restructure_fetch_prospects(client_sdr_id)

    return jsonify({"message": "Success", "data": results}), 200


@PROSPECTING_BLUEPRINT.route("/companydetail", methods=["GET"])
@require_user
def get_company_details(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True, parameter_type=int
    )

    results = fetch_company_details(client_sdr_id, prospect_id)

    return results


@PROSPECTING_BLUEPRINT.route("/apollo_scrape", methods=["POST"])
@require_user
def post_apollo_scrape(client_sdr_id: int):
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=False, parameter_type=int
    )
    segment_id = get_request_parameter(
        "segment_id", request, json=True, required=False, parameter_type=int
    )

    upsert_and_run_apollo_upload_for_sdr(
        client_sdr_id=client_sdr_id,
        name=name,
        archetype_id=archetype_id,
        segment_id=segment_id,
    )

    return jsonify({"message": "Success"}), 200


@PROSPECTING_BLUEPRINT.route("/apollo_scrape", methods=["GET"])
@require_user
def get_apollo_scrapes(client_sdr_id: int):
    results = get_apollo_scraper_jobs(client_sdr_id)

    return jsonify({"message": "Success", "data": results}), 200


@PROSPECTING_BLUEPRINT.route("/apollo_scrape", methods=["PATCH"])
@require_user
def patch_apollo_scrape(client_sdr_id: int):
    job_id = get_request_parameter(
        "job_id", request, json=True, required=True, parameter_type=int
    )
    name = get_request_parameter(
        "name", request, json=True, required=False, parameter_type=str
    )
    active = get_request_parameter(
        "active", request, json=True, required=False, parameter_type=bool
    )
    update_filters = get_request_parameter(
        "update_filters", request, json=True, required=False, parameter_type=bool
    )

    result = update_apollo_scraper_job(
        job_id=job_id,
        name=name,
        active=active,
        update_filters=update_filters,
    )

    return jsonify({"message": "Success", "data": result}), 200


@PROSPECTING_BLUEPRINT.route("/champion/get_champion_changes", methods=["GET"])
@require_user
def get_champion_changes(client_sdr_id: int):
    search_term = request.args.get("search", default=None, type=str)
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()
    client_id = client_sdr.client_id
    results = get_champion_detection_changes(client_id, search_term=search_term)

    return jsonify({"message": "Success", "data": results}), 200


@PROSPECTING_BLUEPRINT.route("/champion/refresh_job_data", methods=["POST"])
@require_user
def post_refresh_champion_job_data(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()
    client_id = client_sdr.client_id
    success = refresh_job_data_for_all_champions(client_id)

    if success:
        return jsonify({"message": "Success"}), 200
    return jsonify({"message": "Failed to refresh job data"}), 400


@PROSPECTING_BLUEPRINT.route("/champion/get_stats", methods=["GET"])
@require_user
def get_champion_stats(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()
    client_id = client_sdr.client_id
    results = get_champion_detection_stats(client_id)

    return jsonify({"message": "Success", "data": results}), 200


@PROSPECTING_BLUEPRINT.route("/champion/mark_champions", methods=["POST"])
@require_user
def post_mark_champions(client_sdr_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )
    is_champion = get_request_parameter(
        "is_champion", request, json=True, required=True, parameter_type=bool
    )

    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()
    client_id = client_sdr.client_id
    success = mark_prospects_as_champion(
        client_id=client_id, prospect_ids=prospect_ids, is_champion=is_champion
    )

    if success:
        return jsonify({"message": "Success"}), 200
    return jsonify({"message": "Failed to mark champions"}), 400
