from typing import List
from flask import Blueprint, request, jsonify
from src.automation.orchestrator import add_process_for_future
from src.message_generation.email.services import get_email_automated_reply_entry
from src.smartlead.services import (
    generate_smart_email_response,
    create_smartlead_campaign,
    get_archetype_emails,
    get_message_history_for_prospect,
    get_smartlead_inbox,
    smartlead_reply_to_prospect,
    set_campaign_id,
    sync_campaign_leads_for_sdr,
    toggle_email_account_for_archetype,
    update_smartlead_campaign_tracking_settings,
)
from app import db
import os
from src.authentication.decorators import require_user
from src.utils.datetime.dateparse_utils import convert_string_to_datetime_or_none
from src.utils.request_helpers import get_request_parameter
from src.smartlead.services import get_campaign_sequence_by_id


SMARTLEAD_BLUEPRINT = Blueprint("smartlead", __name__)


@SMARTLEAD_BLUEPRINT.route("/campaigns/sequence", methods=["GET"])
@require_user
def get_campaigns_sequence(client_sdr_id: int):
    campaign_id = get_request_parameter(
        "campaign_id", request, json=False, required=True, parameter_type=int
    )
    sequence = get_campaign_sequence_by_id(campaign_id=campaign_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": {"sequence": sequence},
            }
        ),
        200,
    )


@SMARTLEAD_BLUEPRINT.route("/campaigns/create", methods=["POST"])
@require_user
def post_create_campaign(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    sync_to_archetype = get_request_parameter(
        "sync_to_archetype", request, json=True, required=False, parameter_type=bool
    )

    success, reason, id = create_smartlead_campaign(
        archetype_id=archetype_id,
        sync_to_archetype=sync_to_archetype,
    )
    if not success:
        return (
            jsonify(
                {
                    "message": reason,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "message": "Success",
                "data": {"campaign_id": id},
            }
        ),
        200,
    )


@SMARTLEAD_BLUEPRINT.route("/campaigns", methods=["POST"])
@require_user
def post_sync_campaigns(client_sdr_id: int):
    sync_campaign_leads_for_sdr.delay(client_sdr_id)

    return jsonify({"message": "Success", "data": {}}), 200


@SMARTLEAD_BLUEPRINT.route("/campaign/settings/tracking", methods=["POST"])
@require_user
def post_campaign_settings_tracking(client_sdr_id: int):
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True, parameter_type=int
    )
    track_open = get_request_parameter(
        "track_open", request, json=True, required=False, parameter_type=bool
    )
    track_link = get_request_parameter(
        "track_link", request, json=True, required=False, parameter_type=bool
    )

    success = update_smartlead_campaign_tracking_settings(
        campaign_id=campaign_id,
        track_open=track_open,
        track_link=track_link,
    )
    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to update tracking settings",
                }
            ),
            400,
        )

    return jsonify({"status": "success"}), 200


@SMARTLEAD_BLUEPRINT.route("/prospect/replied", methods=["GET"])
@require_user
def get_prospects_replied(client_sdr_id: int):
    inbox = get_smartlead_inbox(client_sdr_id=client_sdr_id)

    return (
        jsonify({"message": "Success", "data": {"inbox": inbox}}),
        200,
    )


@SMARTLEAD_BLUEPRINT.route("/prospect/conversation")
@require_user
def get_prospect_conversation(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True, parameter_type=int
    )
    smartlead_campaign_id = (
        get_request_parameter(
            "smartlead_campaign_id",
            request,
            json=False,
            required=False,
            parameter_type=int,
        )
        or None
    )

    conversation = get_message_history_for_prospect(
        prospect_id=prospect_id,
        smartlead_campaign_id=smartlead_campaign_id,
    )

    automated_replies = get_email_automated_reply_entry(
        prospect_id=prospect_id,
    )
    automated_reply = automated_replies[0] if automated_replies else None

    return (
        jsonify(
            {
                "message": "Success",
                "data": {
                    "conversation": conversation,
                    "automated_reply": automated_reply,
                },
            }
        ),
        200,
    )


@SMARTLEAD_BLUEPRINT.route("/prospect/conversation", methods=["POST"])
@require_user
def post_prospect_conversation(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    email_body = get_request_parameter(
        "email_body", request, json=True, required=True, parameter_type=str
    )
    cc_emails = get_request_parameter(
        "cc_emails", request, json=True, required=False, parameter_type=list
    )
    bcc_emails = get_request_parameter(
        "bcc_emails", request, json=True, required=False, parameter_type=list
    )
    scheduled_send_date = get_request_parameter(
        "scheduled_send_date", request, json=True, required=False, parameter_type=str
    )
    scheduled_send_date = (
        convert_string_to_datetime_or_none(scheduled_send_date)
        if scheduled_send_date
        else None
    )

    # If scheduled send date is in the future, add a process to send the email
    if scheduled_send_date:
        success = add_process_for_future(
            type="smartlead_reply_to_prospect",
            args={
                "prospect_id": prospect_id,
                "email_body": email_body,
                "cc": cc_emails,
                "bcc": bcc_emails,
            },
            relative_time=scheduled_send_date,
        )
    else:  # Otherwise, send the email now
        success = smartlead_reply_to_prospect(
            prospect_id=prospect_id, email_body=email_body, cc=cc_emails, bcc=bcc_emails
        )

    if not success:
        return (
            jsonify(
                {
                    "message": "Failed",
                    "data": {"success": success},
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "message": "Success",
                "data": {"success": success},
            }
        ),
        200,
    )


@SMARTLEAD_BLUEPRINT.route("/set_campaign", methods=["POST"])
@require_user
def post_set_campaign(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True, parameter_type=int
    )

    success = set_campaign_id(archetype_id, campaign_id)

    return jsonify({"message": "Success", "data": success}), 200


@SMARTLEAD_BLUEPRINT.route("/generate_smart_response", methods=["POST"])
@require_user
def post_generate_smart_response(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    conversation = get_request_parameter(
        "conversation", request, json=True, required=True, parameter_type=list
    )

    message = generate_smart_email_response(client_sdr_id, prospect_id, conversation)

    return jsonify({"message": "Success", "message": message}), 200


@SMARTLEAD_BLUEPRINT.route("/sync_prospects_to_campaign", methods=["POST"])
@require_user
def post_set_client_sdr_id(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )


@SMARTLEAD_BLUEPRINT.route("/archetype_emails", methods=["GET"])
@require_user
def get_archetype_emails_endpoint(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True, parameter_type=int
    )

    emails = get_archetype_emails(archetype_id=archetype_id)

    return jsonify({"message": "Success", "data": emails}), 200


@SMARTLEAD_BLUEPRINT.route("/toggle_email_accounts", methods=["POST"])
@require_user
def post_toggle_email_accounts_endpoint(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    email_account_ids = get_request_parameter(
        "email_account_ids", request, json=True, required=True, parameter_type=list
    )
    active = get_request_parameter(
        "active", request, json=True, required=True, parameter_type=bool
    )

    success, msg = toggle_email_account_for_archetype(
        archetype_id=archetype_id,
        email_account_ids=email_account_ids,
        enable=active,
    )

    return (
        jsonify({"message": "Success", "data": {"success": success, "message": msg}}),
        200,
    )
