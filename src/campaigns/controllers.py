from flask import Blueprint, request, jsonify

from src.campaigns.agi_campaign_services import create_agi_campaign
from src.campaigns.services import (
    create_outbound_campaign,
    change_campaign_status,
    get_client_campaign_view_data,
    mark_campaign_as_ready_to_send,
    mark_campaign_as_initial_review_complete,
    get_outbound_data,
)
from src.campaigns.autopilot.services import (
    auto_send_campaigns_and_send_approved_messages_job,
)
from src.client.sdr.services_client_sdr import load_sla_schedules
from src.utils.datetime.dateparse_utils import convert_string_to_datetime
from src.utils.request_helpers import get_request_parameter
from model_import import OutboundCampaign
from src.campaigns.services import (
    get_outbound_campaign_details,
    get_outbound_campaign_details_for_edit_tool,
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
    get_outbound_campaign_analytics,
    update_campaign_cost,
    update_campaign_receipt_link,
    wipe_campaign_generations,
    email_analytics,
    payout_campaigns,
    get_account_based_data,
    create_campaign_ai_request,
)
from src.campaigns.autopilot.services import (
    collect_and_generate_all_autopilot_campaigns,
)
from src.message_generation.services import wipe_message_generation_job_queue
from src.authentication.decorators import require_user

CAMPAIGN_BLUEPRINT = Blueprint("campaigns", __name__)


@CAMPAIGN_BLUEPRINT.route("/<campaign_id>", methods=["GET"])
@require_user
def get_campaign_details(client_sdr_id: int, campaign_id: int):
    """Get details for a given campaign."""
    get_messages = get_request_parameter(
        "get_messages",
        request,
        json=False,
        required=False,
        parameter_type=str,
    )
    if get_messages and get_messages.lower() == "true":
        get_messages = True
    else:
        get_messages = False

    shallow_details = get_request_parameter(
        "shallow_details",
        request,
        json=False,
        required=False,
        parameter_type=str,
    )
    if shallow_details and shallow_details.lower() == "true":
        shallow_details = True
    else:
        shallow_details = False

    oc_details = get_outbound_campaign_details(
        client_sdr_id,
        campaign_id=campaign_id,
        get_messages=get_messages,
        shallow_details=shallow_details,
    )
    status_code = oc_details.get("status_code")
    if status_code != 200:
        return jsonify({"message": oc_details.get("message")}), status_code

    return (
        jsonify(
            {
                "message": "Success",
                "campaign_details": oc_details.get("campaign_details"),
            }
        ),
        200,
    )


@CAMPAIGN_BLUEPRINT.route("/uuid/<campaign_uuid>", methods=["GET"])
def get_campaign_details_by_uuid(campaign_uuid: str):
    """Get details for a given campaign, given the UUID. Mainly used for UW editing."""
    campaign: OutboundCampaign = OutboundCampaign.query.filter(
        OutboundCampaign.uuid == campaign_uuid
    ).first()
    if not campaign:
        return jsonify({"message": "Campaign not found."}), 404

    approved_filter = get_request_parameter(
        "approved_filter", request, json=False, required=False, parameter_type=str
    )
    if approved_filter and approved_filter.lower() == "true":
        approved_filter = True
    elif approved_filter and approved_filter.lower() == "false":
        approved_filter = False
    else:
        approved_filter = None

    oc_details = get_outbound_campaign_details_for_edit_tool(
        client_sdr_id=campaign.client_sdr_id,
        campaign_id=campaign.id,
        approved_filter=approved_filter,
    )
    status_code = oc_details.get("status_code")
    if status_code != 200:
        return jsonify({"message": oc_details.get("message")}), status_code

    return (
        jsonify(
            {
                "message": "Success",
                "campaign_details": oc_details.get("campaign_details"),
            }
        ),
        200,
    )


@CAMPAIGN_BLUEPRINT.route("/all_campaigns", methods=["POST"])
@require_user
def get_all_campaigns(client_sdr_id: int):
    """Get all campaigns for a given client sdr."""
    try:
        query = (
            get_request_parameter(
                "query", request, json=True, required=False, parameter_type=str
            )
            or ""
        )
        campaign_start_date = (
            get_request_parameter(
                "campaign_start_date",
                request,
                json=True,
                required=False,
                parameter_type=str,
            )
            or None
        )
        campaign_end_date = (
            get_request_parameter(
                "campaign_end_date",
                request,
                json=True,
                required=False,
                parameter_type=str,
            )
            or None
        )
        campaign_type = (
            get_request_parameter(
                "campaign_type", request, json=True, required=False, parameter_type=list
            )
            or None
        )
        status = (
            get_request_parameter(
                "status", request, json=True, required=False, parameter_type=list
            )
            or None
        )
        limit = (
            get_request_parameter(
                "limit", request, json=True, required=False, parameter_type=int
            )
            or 10
        )
        offset = (
            get_request_parameter(
                "offset", request, json=True, required=False, parameter_type=int
            )
            or 0
        )
        filters = (
            get_request_parameter(
                "filters", request, json=True, required=False, parameter_type=list
            )
            or []
        )
        archetype_id = (
            get_request_parameter(
                "archetype_id", request, json=True, required=False, parameter_type=int
            )
            or None
        )
        include_analytics = (
            get_request_parameter(
                "include_analytics",
                request,
                json=True,
                required=False,
                parameter_type=bool,
            )
        ) or False
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
        archetype_id=archetype_id,
        query=query,
        campaign_start_date=campaign_start_date,
        campaign_end_date=campaign_end_date,
        campaign_type=campaign_type,
        status=status,
        limit=limit,
        offset=offset,
        filters=filters,
    )

    total_count = outbound_campaigns_info.get("total_count")
    outbound_campaigns: list[OutboundCampaign] = outbound_campaigns_info.get(
        "outbound_campaigns"
    )

    campaigns = []
    if include_analytics:
        for outbound_campaign in outbound_campaigns:
            info: dict = outbound_campaign.to_dict()
            info["analytics"] = get_outbound_campaign_analytics(outbound_campaign.id)
            campaigns.append(info)
    else:
        campaigns = [oc.to_dict() for oc in outbound_campaigns]

    return (
        jsonify(
            {
                "message": "Success",
                "total_count": total_count,
                "outbound_campaigns": campaigns,
            }
        ),
        200,
    )


@CAMPAIGN_BLUEPRINT.route("/", methods=["POST"])
@require_user
def create_new_campaign(client_sdr_id: int):
    from model_import import GeneratedMessageType

    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )
    num_prospects = get_request_parameter(
        "num_prospects", request, json=True, required=True, parameter_type=int
    )
    campaign_type = get_request_parameter(
        "campaign_type", request, json=True, required=True, parameter_type=str
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )
    campaign_start_date = get_request_parameter(
        "campaign_start_date", request, json=True, required=True, parameter_type=str
    )
    campaign_end_date = get_request_parameter(
        "campaign_end_date", request, json=True, required=True, parameter_type=str
    )
    ctas = get_request_parameter(
        "ctas", request, json=True, required=False, parameter_type=list
    )
    priority_rating = get_request_parameter(
        "priority_rating", request, json=True, required=False, parameter_type=int
    )
    warm_emails = get_request_parameter(
        "warm_emails", request, json=True, required=False, parameter_type=bool
    )

    # Turn campaign type from string to enum
    if campaign_type == "EMAIL":
        campaign_type = GeneratedMessageType.EMAIL
    elif campaign_type == "LINKEDIN":
        campaign_type = GeneratedMessageType.LINKEDIN

    try:
        campaign: OutboundCampaign = create_outbound_campaign(
            prospect_ids=prospect_ids,
            num_prospects=num_prospects,
            campaign_type=campaign_type,
            ctas=ctas,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            campaign_start_date=campaign_start_date,
            campaign_end_date=campaign_end_date,
            priority_rating=priority_rating,
            warm_emails=warm_emails,
        )
        return jsonify({"campaign_id": campaign.id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@CAMPAIGN_BLUEPRINT.route("/instant", methods=["POST"])
@require_user
def create_new_instant_campaign(client_sdr_id: int):
    from model_import import GeneratedMessageType, OutboundCampaignStatus
    from src.prospecting.services import send_li_outreach_connection

    campaign_type = get_request_parameter(
        "campaign_type", request, json=True, required=True, parameter_type=str
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )
    campaign_start_date = get_request_parameter(
        "campaign_start_date", request, json=True, required=True, parameter_type=str
    )
    campaign_end_date = get_request_parameter(
        "campaign_end_date", request, json=True, required=True, parameter_type=str
    )
    priority_rating = get_request_parameter(
        "priority_rating", request, json=True, required=True, parameter_type=int
    )
    config_id = get_request_parameter(
        "config_id", request, json=True, required=True, parameter_type=int
    )

    # messages type: { prospect_id: int, message: str, cta_id: str, }[]
    messages = get_request_parameter(
        "messages", request, json=True, required=True, parameter_type=list
    )

    # Turn campaign type from string to enum
    if campaign_type == "EMAIL":
        campaign_type = GeneratedMessageType.EMAIL
    elif campaign_type == "LINKEDIN":
        campaign_type = GeneratedMessageType.LINKEDIN

    prospect_ids = list(set([message["prospect_id"] for message in messages]))
    ctas = list(set([message["cta_id"] for message in messages]))

    try:
        campaign: OutboundCampaign = create_outbound_campaign(
            prospect_ids=prospect_ids,
            num_prospects=len(prospect_ids),
            campaign_type=campaign_type,
            ctas=ctas,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            campaign_start_date=campaign_start_date,
            campaign_end_date=campaign_end_date,
            priority_rating=priority_rating,
        )
        campaign_id = campaign.id

        change_campaign_status(
            campaign_id=campaign_id, status=OutboundCampaignStatus.COMPLETE
        )

        # Create SLA Schedules
        load_sla_schedules(client_sdr_id=client_sdr_id)

        msg_ids = []
        for message in messages:
            msg_id = send_li_outreach_connection(
                message["prospect_id"], message["message"], campaign_id, config_id
            )
            msg_ids.append(msg_id)

        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "campaign_id": campaign_id,
                        "message_ids": msg_ids,
                    },
                }
            ),
            200,
        )
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


@CAMPAIGN_BLUEPRINT.route("/<campaign_id>/generate", methods=["POST"])
@require_user
def post_generate_campaigns(client_sdr_id: int, campaign_id: int):
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign.client_sdr_id != client_sdr_id:
        return (
            jsonify(
                {"error": "Unauthorized: this campaign does not belong to this user."}
            ),
            401,
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


@CAMPAIGN_BLUEPRINT.route("/update_campaign_receipt_link", methods=["POST"])
def post_update_campaign_receipt_link():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    receipt_link = get_request_parameter(
        "receipt_link", request, json=True, required=True, parameter_type=str
    )
    update_campaign_receipt_link(campaign_id=campaign_id, receipt_link=receipt_link)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/update_campaign_cost", methods=["POST"])
def post_update_campaign_cost():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    cost = get_request_parameter(
        "cost", request, json=True, required=True, parameter_type=float
    )
    update_campaign_cost(campaign_id=campaign_id, cost=cost)
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


@CAMPAIGN_BLUEPRINT.route("/create_campaign_ai_request", methods=["POST"])
@require_user
def post_create_campaign_ai_request(client_sdr_id: int):

    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=True, parameter_type=str
    )
    linkedin = get_request_parameter(
        "linkedin", request, json=True, required=True, parameter_type=bool
    )
    email = get_request_parameter(
        "email", request, json=True, required=True, parameter_type=bool
    )

    created = create_campaign_ai_request(
        sdr_id=client_sdr_id,
        name=name,
        description=description,
        linkedin=linkedin,
        email=email,
    )

    return (
        jsonify(
            {
                "status": "success",
                "data": created,
            }
        ),
        200,
    )


@CAMPAIGN_BLUEPRINT.route("/get_campaign_analytics", methods=["GET"])
def get_campaign_analytics() -> tuple[dict, int]:
    """Gets campaign analytics, given a campaign_id

    Returns:
        tuple[dict, int]: A tuple containing a dictionary of campaign analytics and a status code
    """
    campaign_id = get_request_parameter(
        "campaign_id", request, json=False, required=True, parameter_type=int
    )
    campaign_analytics = get_outbound_campaign_analytics(campaign_id)

    return campaign_analytics, 200


@CAMPAIGN_BLUEPRINT.route("/<campaign_id>/reset", methods=["POST"])
@require_user
def post_reset_campaign(client_sdr_id: int, campaign_id: int):
    """Reset the given campaign."""

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({"message": "Campaign not found"}), 404
    if campaign.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Unauthorized"}), 401

    wipe_campaign_generations.apply_async(args=[campaign_id], priority=2)

    wipe_message_generation_job_queue.apply_async(args=[campaign_id], priority=2)

    return jsonify({"message": "Starting campaign reset"}), 200


@CAMPAIGN_BLUEPRINT.route("/email_analytics", methods=["GET"])
@require_user
def get_email_analytics(client_sdr_id: int):
    """Gets email analytics by sequence

    Returns:
        status: The email analytics
    """
    result = email_analytics(client_sdr_id)

    return jsonify(result), result.get("status_code")


@CAMPAIGN_BLUEPRINT.route("/autopilot/generate_all_campaigns", methods=["POST"])
def generate_all_autopilot_campaigns_endpoint():
    """Generate all autopilot campaigns."""
    start_date = get_request_parameter(
        "start_date", request, json=True, required=False, parameter_type=str
    )
    start_date = convert_string_to_datetime(start_date) if start_date else None

    collect_and_generate_all_autopilot_campaigns(start_date=start_date)
    return "OK", 200


@CAMPAIGN_BLUEPRINT.route("/remove_prospect/<int:prospect_id>", methods=["DELETE"])
def delete_prospect_from_campaign(prospect_id: int):
    """Remove a prospect from a campaign."""
    from src.campaigns.services import remove_prospect_from_campaign

    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )

    success = remove_prospect_from_campaign(
        campaign_id=campaign_id, prospect_id=prospect_id
    )
    if success:
        return "OK", 200
    return "Failed to remove prospect from campaign", 400


@CAMPAIGN_BLUEPRINT.route("/payout_campaigns", methods=["POST"])
def post_payout_campaigns():
    """
    Mark the campaigns as paid out by marking receipt and cost
    """
    campaign_ids = get_request_parameter(
        "campaign_ids", request, json=True, required=True
    )

    success = payout_campaigns(campaign_ids=campaign_ids)

    if success:
        return "OK", 200

    return "Failed to payout campaigns", 400


@CAMPAIGN_BLUEPRINT.route("/client_campaign_view_data", methods=["POST"])
@require_user
def post_client_campaign_view_data(client_sdr_id: int):
    """
    Gets the data for the client campaign view
    """

    records = get_client_campaign_view_data(client_sdr_id=client_sdr_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "records": records,
                },
            }
        ),
        200,
    )


@CAMPAIGN_BLUEPRINT.route("/create_agi_campaign", methods=["POST"])
@require_user
def post_create_agi_campaign(client_sdr_id: int):
    """
    Finds prospects and creates copy from a given request.
    """
    query = get_request_parameter("query", request, json=True, required=True)
    campaign_instruction = get_request_parameter(
        "campaign_instruction", request, json=True, required=True
    )
    run_prospecting = get_request_parameter(
        "run_prospecting",
        request,
        json=True,
        required=False,
        parameter_type=bool,
        default_value=True,
    )
    run_linkedin = get_request_parameter(
        "run_linkedin",
        request,
        json=True,
        required=False,
        parameter_type=bool,
        default_value=True,
    )
    run_email = get_request_parameter(
        "run_email",
        request,
        json=True,
        required=False,
        parameter_type=bool,
        default_value=True,
    )

    data = create_agi_campaign(
        client_sdr_id=client_sdr_id,
        query=query,
        campaign_instruction=campaign_instruction,
        run_prospecting=run_prospecting,
        run_linkedin=run_linkedin,
        run_email=run_email,
    )

    return jsonify(data)


@CAMPAIGN_BLUEPRINT.route("/utilization", methods=["GET"])
@require_user
def get_outboundData(client_sdr_id: int):
    data = get_outbound_data(client_sdr_id)

    return data


@CAMPAIGN_BLUEPRINT.route("/account_based", methods=["POST"])
@require_user
def get_account_based_view_data(client_sdr_id: int):

    offset: int = get_request_parameter("offset", request, json=True, required=True)

    data = get_account_based_data(client_sdr_id=client_sdr_id, offset=offset)

    return (
        jsonify(
            {
                "status": "success",
                "data": data,
            }
        ),
        200,
    )
