from flask import Blueprint, request, jsonify

from src.campaigns.services import (
    create_outbound_campaign,
    change_campaign_status,
    mark_campaign_as_ready_to_send,
    mark_campaign_as_initial_review_complete,
)
from src.utils.request_helpers import get_request_parameter
from model_import import OutboundCampaign
from src.campaigns.services import (
    generate_campaign,
    update_campaign_dates,
    update_campaign_name,
    merge_outbound_campaigns,
    batch_update_campaigns,
)

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


@CAMPAIGN_BLUEPRINT.route("/batch", methods=["PATCH"])
def patch_batch_update_campaigns():
    payload = get_request_parameter("payload", request, json=True, required=True)
    success = batch_update_campaigns(payload=payload)
    if success:
        return "OK", 200
    return "Failed to update", 400


@CAMPAIGN_BLUEPRINT.route("/generate", methods=["POST"])
def post_generate_campaigns():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    generate_campaign(campaign_id=campaign_id)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/mark_initial_review_complete", methods=["POST"])
def post_mark_initial_review_complete():
    """Mark a campaign as ready to send and send a slack message to the operations channel.

    Returns:
        status: 200 if successful, 400 if failed
    """
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    success = mark_campaign_as_initial_review_complete(campaign_id=campaign_id)
    if success:
        return "OK", 200

    return "Failed to mark", 400


@CAMPAIGN_BLUEPRINT.route("/mark_ready_to_send", methods=["POST"])
def post_mark_campaign_as_ready_to_send():
    """Mark a campaign as ready to send and send a slack message to the operations channel.

    Returns:
        status: 200 if successful, 400 if failed
    """
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    success = mark_campaign_as_ready_to_send(campaign_id=campaign_id)
    if success:
        return "OK", 200

    return "Failed to mark", 400


@CAMPAIGN_BLUEPRINT.route("/update_campaign_name", methods=["POST"])
def post_update_campaign_name():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    name = get_request_parameter("name", request, json=True, required=True)
    update_campaign_name(campaign_id=campaign_id, name=name)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/update_campaign_dates", methods=["POST"])
def post_update_campaign_dates():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    start_date = get_request_parameter("start_date", request, json=True, required=True)
    end_date = get_request_parameter("end_date", request, json=True, required=True)
    update_campaign_dates(
        campaign_id=campaign_id, start_date=start_date, end_date=end_date
    )
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/merge", methods=["POST"])
def post_merge_campaigns():
    campaign_ids = get_request_parameter(
        "campaign_ids", request, json=True, required=True
    )
    try:
        campaign_id = merge_outbound_campaigns(campaign_ids=campaign_ids)
    except Exception as e:
        return str(e), 400
    return jsonify({"new_campaign_id": campaign_id})
