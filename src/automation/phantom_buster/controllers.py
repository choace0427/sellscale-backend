from flask import Blueprint, jsonify, request
from src.utils.csv import send_csv
from src.authentication.decorators import require_user
from src.automation.models import PhantomBusterSalesNavigatorLaunch
from src.automation.phantom_buster.services import (
    collect_and_load_sales_navigator_results,
    create_phantom_buster_sales_navigator_config,
    get_sales_navigator_launch_result,
    get_sales_navigator_launches,
    register_phantom_buster_sales_navigator_url,
    reset_sales_navigator_launch,
    register_phantom_buster_sales_navigator_account_filters_url,
    run_outbound_phantoms_for_sdrs,
)
from src.utils.converters.dictionary_converters import dictionary_normalization

from src.utils.request_helpers import get_request_parameter


PHANTOM_BUSTER_BLUEPRINT = Blueprint("automation/phantom_buster", __name__)


@PHANTOM_BUSTER_BLUEPRINT.route("/")
def index():
    return jsonify({"status": "success", "data": {}}), 200


@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/", methods=["POST"])
def create_phantom_buster_sales_navigator():
    client_sdr_id: int = get_request_parameter("client_sdr_id", request, json=True)
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
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=False, required=False
    )

    launches = get_sales_navigator_launches(
        client_sdr_id=client_sdr_id, client_archetype_id=client_archetype_id
    )

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
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=False, parameter_type=int
    )
    process_type = get_request_parameter(
        "process_type", request, json=True, required=False, parameter_type=str
    )

    success, _ = register_phantom_buster_sales_navigator_url(
        sales_navigator_url=sales_navigator_url,
        scrape_count=scrape_count,
        client_sdr_id=client_sdr_id,
        scrape_name=name,
        client_archetype_id=client_archetype_id,
        process_type=process_type,
    )
    if not success:
        return (
            jsonify({"status": "error", "message": "Launch not available. Try again."}),
            404,
        )

    return jsonify({"status": "success", "message": "Launch registered"}), 200


@PHANTOM_BUSTER_BLUEPRINT.route(
    "/sales_navigator/launch/<int:launch_id>/reset", methods=["POST"]
)
@require_user
def reset_sales_navigator_launch_endpoint(client_sdr_id: int, launch_id: int):
    """Resets the specific launch data for a given launch ID"""
    launch: PhantomBusterSalesNavigatorLaunch = (
        PhantomBusterSalesNavigatorLaunch.query.get(launch_id)
    )
    if launch.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    reset_sales_navigator_launch(launch_id=launch_id, client_sdr_id=client_sdr_id)

    return jsonify({"status": "success", "message": "Launch reset"}), 200


@PHANTOM_BUSTER_BLUEPRINT.route(
    "/sales_navigator/launch/<int:launch_id>", methods=["GET"]
)
@require_user
def get_sales_navigator_launch_endpoint(client_sdr_id: int, launch_id: int):
    """Gets the specific launch data for a given launch ID"""
    launch: PhantomBusterSalesNavigatorLaunch = (
        PhantomBusterSalesNavigatorLaunch.query.get(launch_id)
    )
    if launch.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    launch_raw, launch_processed = get_sales_navigator_launch_result(
        client_sdr_id=client_sdr_id, launch_id=launch_id
    )
    if not launch_raw:
        return jsonify({"status": "error", "message": "Launch not available"}), 404

    # Only pull specific columns from the dictionary
    selected_keys = ["fullName", "title", "companyName", "linkedInProfileUrl"]
    renamed_keys = ["full_name", "title", "company", "linkedin_url"]
    condensed_csv = [
        {
            new_key: item[old_key]
            for old_key, new_key in zip(selected_keys, renamed_keys)
        }
        for item in launch_processed
    ]
    headers = set(renamed_keys)

    # Normalize dictionary data
    dictionary_normalization(keys=headers, dictionaries=condensed_csv)

    return send_csv(condensed_csv, "launch_results.csv", headers)

@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/launch/<int:launch_id>/account_filters_url", methods=["PATCH"])
@require_user
def update_sales_navigator_launch_account_filters_url(client_sdr_id: int, launch_id: int):
    """Registers the account_filters_url for a given launch ID"""
    account_filters_url = get_request_parameter(
        "account_filters_url", request, json=True, required=True, parameter_type=str
    )

    success = register_phantom_buster_sales_navigator_account_filters_url(
        launch_id=launch_id,
        client_sdr_id=client_sdr_id,
        account_filters_url=account_filters_url
    )

    if success:
        return jsonify({"status": "success", "message": "URL updated successfully"}), 200
    else:
        return jsonify({"status": "error", "message": "Update failed"}), 400


@PHANTOM_BUSTER_BLUEPRINT.route("/sales_navigator/webhook", methods=["POST"])
def sales_navigator_webhook():
    """Webhook for sales navigator"""
    collect_and_load_sales_navigator_results.delay()

    return jsonify({"status": "success", "data": {}}), 200

@PHANTOM_BUSTER_BLUEPRINT.route("/run_phantoms_for_sdrs", methods=["POST"])
def run_phantoms_for_sdrs():
    """Run phantoms for all SDRs"""
    client_sdr_ids = get_request_parameter("client_sdr_ids", request, json=True, required=True)

    run_outbound_phantoms_for_sdrs(
        client_sdr_ids=client_sdr_ids
    )

    return jsonify({"status": "success", "data": {}}), 200