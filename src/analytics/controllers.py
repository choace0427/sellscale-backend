from flask import Blueprint, request, jsonify
from src.utils.request_helpers import get_request_parameter
from src.analytics.services import (
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
