from typing import List
from flask import Blueprint, request, jsonify
from src.message_generation.email.services import get_email_automated_reply_entry
from src.smartlead.services import (
    generate_smart_email_response,
    create_smartlead_campaign,
    get_message_history_for_prospect,
    get_smartlead_inbox,
    reply_to_prospect,
    set_campaign_id,
    sync_campaign_leads_for_sdr,
)
from app import db
import os
from src.authentication.decorators import require_user
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

    success = reply_to_prospect(prospect_id=prospect_id, email_body=email_body)
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


# DEPRECATED
# @SMARTLEAD_BLUEPRINT.route("/sync_prospects_to_campaign", methods=["POST"])
# @require_user
# def post_set_client_sdr_id(client_sdr_id: int):
#     archetype_id = get_request_parameter(
#         "archetype_id", request, json=True, required=True, parameter_type=int
#     )

#     success, amount = sync_prospects_to_campaign(client_sdr_id, archetype_id)

#     return (
#         jsonify({"message": "Success", "data": {"success": success, "amount": amount}}),
#         200,
#     )
