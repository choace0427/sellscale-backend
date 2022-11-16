from flask import Blueprint, request, jsonify

from src.campaigns.services import create_outbound_campaign, change_campaign_status
from src.utils.request_helpers import get_request_parameter
from model_import import OutboundCampaign
from src.campaigns.services import generate_campaign

CAMPAIGN_BLUEPRINT = Blueprint("campaigns", __name__)


@CAMPAIGN_BLUEPRINT.route("/", methods=["POST"])
def create_new_campaign():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )
    campaign_type = get_request_parameter(
        "campaign_type", request, json=True, required=True
    )
    ctas = get_request_parameter("ctas", request, json=True, required=False)
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    campaign_start_date = get_request_parameter(
        "campaign_start_date", request, json=True, required=True
    )
    campaign_end_date = get_request_parameter(
        "campaign_end_date", request, json=True, required=True
    )
    email_schema_id = get_request_parameter(
        "email_schema_id", request, json=True, required=False
    )

    campaign: OutboundCampaign = create_outbound_campaign(
        prospect_ids=prospect_ids,
        campaign_type=campaign_type,
        ctas=ctas,
        email_schema_id=email_schema_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date=campaign_start_date,
        campaign_end_date=campaign_end_date,
    )
    return jsonify({"campaign_id": campaign.id}), 200


@CAMPAIGN_BLUEPRINT.route("/", methods=["PATCH"])
def patch_change_campaign_status():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    status = get_request_parameter("status", request, json=True, required=True)
    change_campaign_status(campaign_id=campaign_id, status=status)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/generate", methods=["POST"])
def post_generate_campaigns():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    generate_campaign(campaign_id=campaign_id)
    return "OK", 200
