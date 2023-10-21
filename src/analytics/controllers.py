from flask import Blueprint, request, jsonify
from src.utils.request_helpers import get_request_parameter
from src.analytics.services import (
    get_all_campaign_analytics_for_client,
    get_outreach_over_time,
    get_sdr_pipeline_all_details,
)
from src.authentication.decorators import require_user
from model_import import ClientSDR

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
