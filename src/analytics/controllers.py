from flask import Blueprint, request, jsonify
from src.utils.request_helpers import get_request_parameter
from src.analytics.services import get_li_message_benchmarks_for_client

ANALYTICS_BLUEPRINT = Blueprint("analytics", __name__)


@ANALYTICS_BLUEPRINT.route("/")
def index():
    return "OK", 200


@ANALYTICS_BLUEPRINT.route("/weekly_li_benchmarks", methods=["GET"])
def get_weekly_li_benchmarks():
    client_id = get_request_parameter("client_id", request, json=False, required=True)
    benchmarks = get_li_message_benchmarks_for_client(client_id=client_id)
    return jsonify(benchmarks)
