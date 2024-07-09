from http import client
from flask import Blueprint, request, jsonify
from src.analytics.campaign_drilldown import get_campaign_drilldown_data
from src.analytics.services_chatbot import answer_question, process_data_and_answer
from src.client.models import ClientArchetype
from src.utils.request_helpers import get_request_parameter
from src.analytics.services import (
    add_activity_log,
    get_activity_logs,
    get_cycle_dates_for_campaign,
    get_template_analytics_for_archetype,
    get_all_campaign_analytics_for_client,
    get_all_campaign_analytics_for_client_campaigns_page,
    get_outreach_over_time,
    get_overview_pipeline_activity,
    get_sdr_pipeline_all_details,
    get_upload_analytics_for_client,
)
from src.analytics.services_rejection_analysis import (
    get_rejection_analysis_data,
    get_rejection_report_data,
)
from src.analytics.drywall_notification import notify_clients_with_no_updates
from src.analytics.scheduling_needed_notification import (
    notify_clients_regarding_scheduling,
)
from src.analytics.daily_message_generation_sample import (
    send_report_email,
)
from src.analytics.daily_backfill_response_times_from_sdr import (
    backfill_last_reply_dates_for_conversations_in_last_day,
)
from src.authentication.decorators import require_user
from model_import import ClientSDR
from src.analytics.services_asset_analytics import backfill_all_assets_analytics
from model_import import Prospect
from sqlalchemy import not_

ANALYTICS_BLUEPRINT = Blueprint("analytics", __name__)


@ANALYTICS_BLUEPRINT.route("/")
def index():
    return "OK", 200


@ANALYTICS_BLUEPRINT.route("/pipeline/all_details", methods=["GET"])
@require_user
def get_all_pipeline_details(client_sdr_id: int):
    """Endpoint to get all pipeline details for a given SDR."""

    include_purgatory = get_request_parameter(
        "include_purgatory", request, json=False, required=False
    )
    if include_purgatory is None:
        include_purgatory = False
    else:
        include_purgatory = include_purgatory.lower() == "true"

    details = get_sdr_pipeline_all_details(
        client_sdr_id=client_sdr_id, include_purgatory=include_purgatory
    )

    return {"message": "Success", "pipeline_data": details}, 200


@ANALYTICS_BLUEPRINT.route("/inbox_messages_to_view", methods=["GET"])
@require_user
def get_inbox_messages_to_see(client_sdr_id: int):
    """Endpoint to get the count of messages prospects have sent to us"""

    count = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        not_(
            Prospect.li_is_last_message_from_sdr
            & Prospect.email_is_last_message_from_sdr
        ),
    ).count()

    return {"message": "Success", "data": count}, 200


@ANALYTICS_BLUEPRINT.route("/all_campaign_analytics", methods=["GET"])
@require_user
def get_all_campaign_analytics(client_sdr_id: int):
    """Endpoint to get all campaign analytics for the SDRs in the given SDR's client"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return {"message": "Invalid client SDR ID"}, 400

    details = get_all_campaign_analytics_for_client(client_id=client_sdr.client_id)

    return {"message": "Success", "pipeline_data": details}, 200


@ANALYTICS_BLUEPRINT.route("/outreach_over_time", methods=["GET"])
@require_user
def get_outreach_over_time_endpoint(client_sdr_id: int):
    """Endpoint to get outreach over time for a given SDR."""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return {"message": "Invalid client SDR ID"}, 400

    modes = get_outreach_over_time(client_id=client_sdr.client_id)
    return {"message": "Success", "outreach_over_time": modes}, 200


@ANALYTICS_BLUEPRINT.route("/client_campaign_analytics", methods=["GET"])
@require_user
def get_client_campaign_analytics(client_sdr_id: int):
    """Endpoint to get all campaign analytics for the SDRs in the given SDR's client"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return {"message": "Invalid client SDR ID"}, 400

    details = get_all_campaign_analytics_for_client_campaigns_page(
        client_id=client_sdr.client_id
    )

    return {"message": "Success", "analytics": details}, 200


@ANALYTICS_BLUEPRINT.route("/client_upload_analytics", methods=["GET"])
@require_user
def get_client_upload_analytics(client_sdr_id: int):
    """Endpoint to get all campaign analytics for the SDRs in the given SDR's client"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return {"message": "Invalid client SDR ID"}, 400

    details = get_upload_analytics_for_client(client_id=client_sdr.client_id)

    return {"message": "Success", "analytics": details}, 200


@ANALYTICS_BLUEPRINT.route(
    "/get_campaign_drilldown/<int:archetype_id>", methods=["GET"]
)
@require_user
def get_campaign_drilldown(client_sdr_id: int, archetype_id: int):
    """Endpoint to get all campaign analytics for the SDRs in the given SDR's client"""
    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if client_archetype.client_sdr_id != client_sdr_id:
        return {"message": "Client archetype does not belong to client SDR"}, 400

    details = get_campaign_drilldown_data(archetype_id=archetype_id)

    return {"message": "Success", "analytics": details}, 200


@ANALYTICS_BLUEPRINT.route("/rejection_analysis", methods=["GET"])
@require_user
def get_rejection_analysis(client_sdr_id: int):
    """
    Endpoint to fetch Rejection Analysis data.
    Accepts client_sdr_id and status (NOT_INTERESTED or NOT_QUALIFIED) as query parameters.
    """

    # Extracting 'status' from query parameters
    status = request.args.get("status")

    # Validating 'status' parameter
    if status not in ["NOT_INTERESTED", "NOT_QUALIFIED"]:
        return {"message": "Invalid status parameter"}, 400

    # Validating client_sdr_id
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return {"message": "Invalid client SDR ID"}, 400

    # Fetching data using the service function
    data = get_rejection_analysis_data(client_sdr_id, status)
    return {"message": "Success", "data": data}, 200


@ANALYTICS_BLUEPRINT.route("/rejection_report", methods=["GET"])
@require_user
def rejection_report(client_sdr_id: int):
    """
    Endpoint to fetch Rejection Report details.
    """
    # Validating client_sdr_id
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return {"message": "Invalid client SDR ID"}, 400

    try:
        # Fetching data using the service function
        data = get_rejection_report_data(client_sdr_id)
        return jsonify({"message": "Success", "data": data}), 200
    except Exception as e:
        print(f"Error fetching rejection report details: {e}")
        return jsonify({"message": "Error fetching data", "error": str(e)}), 500


@ANALYTICS_BLUEPRINT.route("/ask", methods=["POST"])
@require_user
def ask_analytics(client_sdr_id: int):
    """
    Endpoint to ask analytics questions.
    """
    # Validating client_sdr_id
    query = get_request_parameter("query", request, json=True, required=True)
    answer = answer_question(client_sdr_id=client_sdr_id, query=query)

    return jsonify({"message": "Success", "answer": answer}), 200


@ANALYTICS_BLUEPRINT.route("/activity_log", methods=["POST"])
@require_user
def post_activity_log_endpoint(client_sdr_id: int):

    type = get_request_parameter("type", request, json=True, required=True)
    name = get_request_parameter("name", request, json=True, required=True)
    description = get_request_parameter(
        "description", request, json=True, required=True
    )

    id = add_activity_log(
        client_sdr_id=client_sdr_id, type=type, name=name, description=description
    )

    return jsonify({"message": "Success", "data": id}), 200


@ANALYTICS_BLUEPRINT.route("/activity_log", methods=["GET"])
@require_user
def get_activity_logs_endpoint(client_sdr_id: int):

    logs = get_activity_logs(client_sdr_id=client_sdr_id)

    return jsonify({"message": "Success", "data": logs}), 200

@ANALYTICS_BLUEPRINT.route("/get_cycle_dates", methods=["GET"])
@require_user
def get_cycle_dates(client_sdr_id: int):
    campaign_id = get_request_parameter("campaignID", request, json=False, required=True)
    print('got campaign id', campaign_id)
    
    try:
        # Assuming there's a service function to fetch cycle dates
        cycle_dates = get_cycle_dates_for_campaign(client_sdr_id, campaign_id)
        return jsonify(cycle_dates), 200
    except Exception as e:
        print(f"Error fetching cycle dates: {e}")
        return jsonify({"message": "Error fetching cycle dates", "error": str(e)}), 500
    

#endpoint to get template analytics
@ANALYTICS_BLUEPRINT.route("/template_analytics", methods=["GET"])
@require_user
def get_template_analytics(client_sdr_id: int):

    archetype_id = get_request_parameter("archetype_id", request, json=False, required=True)
    start_date = get_request_parameter("start_date", request, json=False, required=True)

    data = get_template_analytics_for_archetype(archetype_id, start_date)
    return jsonify({"message": "Success", "data": data}), 200

@ANALYTICS_BLUEPRINT.route("/overview_analytics", methods=["GET"])
@require_user
def get_overview_analytics(client_sdr_id: int):
    data = get_overview_pipeline_activity(client_sdr_id)
    return jsonify({"message": "Success", "data": data}), 200
