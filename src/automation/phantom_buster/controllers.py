from flask import Blueprint, jsonify, request
from flask_csv import send_csv
from src.authentication.decorators import require_user
from src.automation.models import PhantomBusterSalesNavigatorLaunch
from src.automation.phantom_buster.services import collect_and_load_sales_navigator_results, create_phantom_buster_sales_navigator_config, get_sales_navigator_launch_result, get_sales_navigator_launches, register_phantom_buster_sales_navigator_url

from src.utils.request_helpers import get_request_parameter


PHANTOM_BUSTER_BLUEPRINT = Blueprint("automation/phantom_buster", __name__)


@PHANTOM_BUSTER_BLUEPRINT.route("/")
def index():
    return jsonify({"status": "success", "data": {}}), 200


@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/", methods=["POST"])
def create_phantom_buster_sales_navigator():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True
    )
    linkedin_session_cookie = get_request_parameter(
        "linkedin_session_cookie", request, json=True, required=True
    )

    pb_config = create_phantom_buster_sales_navigator_config(
        linkedin_session_cookie=linkedin_session_cookie, client_sdr_id=client_sdr_id
    )

    return jsonify({"status": "success", "data": {"pb_id": pb_config}}), 200


@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/launch", methods=["GET"])
@require_user
def get_sales_navigator_launches_endpoint(client_sdr_id: int):
    """Gets the sales navigator launches for the Client SDR"""
    launches = get_sales_navigator_launches(client_sdr_id=client_sdr_id)

    return jsonify({"status": "success", "data": {"launches": launches}}), 200


@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/launch", methods=["POST"])
@require_user
def post_sales_navigator_launch(client_sdr_id):
    """Posts a sales navigator launch"""
    sales_navigator_url = get_request_parameter(
        "sales_navigator_url", request, json=True, required=True, parameter_type=str
    )
    scrape_count = get_request_parameter(
        "scrape_count", request, json=True, required=True, parameter_type=int
    )

    success, _ = register_phantom_buster_sales_navigator_url(
        sales_navigator_url=sales_navigator_url,
        scrape_count=scrape_count,
        client_sdr_id=client_sdr_id,
    )
    if not success:
        return jsonify({"status": "error", "message": "Launch not available. Try again."}), 404

    return jsonify({"status": "success", "message": "Launch registered"}), 200


@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/launch/<int:launch_id>", methods=["GET"])
@require_user
def get_sales_navigator_launch_endpoint(client_sdr_id: int, launch_id: int):
    """Gets the specific launch data for a given launch ID"""
    launch: PhantomBusterSalesNavigatorLaunch = PhantomBusterSalesNavigatorLaunch.query.get(launch_id)
    if launch.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    launch = get_sales_navigator_launch_result(
        client_sdr_id=client_sdr_id,
        launch_id=launch_id
    )
    if not launch:
        return jsonify({"status": "error", "message": "Launch not available"}), 404

    # Extract headers from the first dictionary
    headers = launch[0].keys()

    # Convert the list of dictionaries to a list of lists
    launch_transformed = [list(headers)] + [list(row.values()) for row in launch]

    return send_csv(launch_transformed, filename="launch_results.csv")


@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/webhook", methods=["POST"])
def sales_navigator_webhook():
    """Webhook for sales navigator"""
    collect_and_load_sales_navigator_results.delay()

    return jsonify({"status": "success", "data": {}}), 200
