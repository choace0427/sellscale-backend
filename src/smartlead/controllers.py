from typing import List
from flask import Blueprint, request, jsonify
from src.smartlead.services import (
    get_message_history_for_prospect,
    get_replied_prospects,
    set_campaign_id,
    sync_campaign_leads_for_sdr,
    sync_prospects_to_campaign,
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


@SMARTLEAD_BLUEPRINT.route("/campaigns", methods=["POST"])
@require_user
def post_sync_campaigns(client_sdr_id: int):
    sync_campaign_leads_for_sdr.delay(client_sdr_id)

    return jsonify({"message": "Success", "data": {}}), 200


@SMARTLEAD_BLUEPRINT.route("/prospect/replied", methods=["GET"])
@require_user
def get_prospects_replied(client_sdr_id: int):
    replied_prospects = get_replied_prospects(client_sdr_id=client_sdr_id)

    return (
        jsonify(
            {"message": "Success", "data": {"replied_prospects": replied_prospects}}
        ),
        200,
    )


@SMARTLEAD_BLUEPRINT.route("/prospect/conversation")
@require_user
def get_prospect_conversation(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True, parameter_type=int
    )
    smartlead_campaign_id = get_request_parameter(
        "smartlead_campaign_id", request, json=False, required=True, parameter_type=int
    )

    conversation = get_message_history_for_prospect(
        prospect_id=prospect_id,
        smartlead_campaign_id=smartlead_campaign_id,
    )

    return (
        jsonify(
            {
                "message": "Success",
                "data": {"conversation": conversation},
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


@SMARTLEAD_BLUEPRINT.route("/sync_prospects_to_campaign", methods=["POST"])
@require_user
def post_set_client_sdr_id(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    success, amount = sync_prospects_to_campaign(client_sdr_id, archetype_id)

    return (
        jsonify({"message": "Success", "data": {"success": success, "amount": amount}}),
        200,
    )
