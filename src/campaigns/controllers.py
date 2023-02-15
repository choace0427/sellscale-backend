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
    get_outbound_campaigns,
    generate_campaign,
    update_campaign_dates,
    update_campaign_name,
    merge_outbound_campaigns,
    batch_update_campaigns,
    split_outbound_campaigns,
    assign_editor_to_campaign,
    batch_update_campaign_editing_attributes,
    adjust_editing_due_date,
    remove_ungenerated_prospects_from_campaign,
    create_new_li_campaign_from_existing_email_campaign,
    get_outbound_campaign_analytics
)
from src.authentication.decorators import require_user

CAMPAIGN_BLUEPRINT = Blueprint("campaigns", __name__)


@CAMPAIGN_BLUEPRINT.route("/all_campaigns", methods=["POST"])
@require_user
def get_all_campaigns(client_sdr_id: int):
    """Get all campaigns for a given client sdr."""
    try:
        query = (
            get_request_parameter(
                "query", request, json=True, required=False, parameter_type=str
            ) or ""
        )
        campaign_type = (
            get_request_parameter(
                "campaign_type", request, json=True, required=False, parameter_type=list
            ) or None
        )
        status = (
            get_request_parameter(
                "status", request, json=True, required=False, parameter_type=list
            ) or None
        )
        limit = (
            get_request_parameter(
                "limit", request, json=True, required=False, parameter_type=int
            ) or 10
        )
        offset = (
            get_request_parameter(
                "offset", request, json=True, required=False, parameter_type=int
            ) or 0
        )
        filters = (
            get_request_parameter(
                "filters", request, json=True, required=False, parameter_type=list
            )
            or []
        )
    except Exception as e:
        return e.args[0], 400

    # Validate the filters
    if filters and len(filters) > 0:
        for filter in filters:
            keys = filter.keys()
            if len(keys) != 2 or keys != {"field", "direction"}:
                return jsonify({"message": "Invalid filters supplied to API"}), 400

    outbound_campaigns_info: dict[int, list[OutboundCampaign]] = get_outbound_campaigns(
        client_sdr_id=client_sdr_id,
        query=query,
        campaign_type=campaign_type,
        status=status,
        limit=limit,
        offset=offset,
        filters=filters,
    )

    total_count = outbound_campaigns_info.get("total_count")
    outbound_campaigns: list[OutboundCampaign] = outbound_campaigns_info.get("outbound_campaigns")

    return jsonify(
        {
            "message": "Success",
            "total_count": total_count,
            "outbound_campaigns": [oc.to_dict() for oc in outbound_campaigns]
        }
    ), 200


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

    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 400


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


@CAMPAIGN_BLUEPRINT.route("/batch_editing_attributes", methods=["PATCH"])
def patch_batch_update_campaign_editing_attributes():
    payload = get_request_parameter("payload", request, json=True, required=True)
    success = batch_update_campaign_editing_attributes(payload=payload)
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


@CAMPAIGN_BLUEPRINT.route("/split", methods=["POST"])
def post_split_campaigns():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    num_campaigns = get_request_parameter(
        "num_campaigns", request, json=True, required=True
    )
    campaign_ids = split_outbound_campaigns(
        original_campaign_id=campaign_id, num_campaigns=num_campaigns
    )
    return jsonify({"campaign_ids": campaign_ids})


@CAMPAIGN_BLUEPRINT.route("/assign_editor", methods=["POST"])
def post_assign_editor():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    editor_id = get_request_parameter("editor_id", request, json=True, required=True)
    assign_editor_to_campaign(editor_id=editor_id, campaign_id=campaign_id)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/adjust_editing_due_date", methods=["POST"])
def post_adjust_editing_due_date():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    new_date = get_request_parameter("new_date", request, json=True, required=True)
    adjust_editing_due_date(campaign_id=campaign_id, new_date=new_date)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/remove_ungenerated_prospects", methods=["POST"])
def post_remove_ungenerated_prospects():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    remove_ungenerated_prospects_from_campaign(campaign_id=campaign_id)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/create_li_campaign_from_email", methods=["POST"])
def post_create_li_campaign_from_email():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    campaign = create_new_li_campaign_from_existing_email_campaign(campaign_id)
    return jsonify({"campaign_id": campaign.id})


@CAMPAIGN_BLUEPRINT.route("/get_campaign_analytics", methods=["GET"])
def get_campaign_analytics() -> tuple[dict, int]:
    """Gets campaign analytics, given a campaign_id

    Returns:
        tuple[dict, int]: A tuple containing a dictionary of campaign analytics and a status code
    """
    campaign_id = get_request_parameter("campaign_id", request, json=False, required=True)
    campaign_analytics = get_outbound_campaign_analytics(campaign_id)

    return campaign_analytics, 200
