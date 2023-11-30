from typing import List
from flask import Blueprint, request, jsonify
from src.smartlead.services import (
    get_email_warmings_for_sdr,
    set_campaign_id,
    sync_prospects_to_campaign,
)
from app import db
import os
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter

SMARTLEAD_BLUEPRINT = Blueprint("smartlead", __name__)


@SMARTLEAD_BLUEPRINT.route("/email_warmings", methods=["GET"])
@require_user
def get_email_warmings(client_sdr_id: int):
    email_warmings = get_email_warmings_for_sdr(client_sdr_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": [warming.to_dict() for warming in email_warmings],
            }
        ),
        200,
    )


@SMARTLEAD_BLUEPRINT.route("/campaigns", methods=["POST"])
@require_user
def post_sync_campaigns(client_sdr_id: int):
    from src.smartlead.services import sync_campaign_leads

    sync_campaign_leads(client_sdr_id=client_sdr_id)

    return jsonify({"message": "Success", "data": {}}), 200


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
