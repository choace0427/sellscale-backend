import json
from flask import Blueprint, request, jsonify
from src.automation.models import PhantomBusterType
from src.client.models import ClientArchetype
from src.client.services import (
    create_client,
    create_client_archetype,
    create_client_sdr,
)
from src.automation.services import create_phantom_buster_config
from src.automation.services import get_all_phantom_busters
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message

AUTOMATION_BLUEPRINT = Blueprint("automation", __name__)


@AUTOMATION_BLUEPRINT.route("/")
def index():
    return "OK", 200


@AUTOMATION_BLUEPRINT.route("/create/phantom_buster_config", methods=["POST"])
def post_phantom_buster_config():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    google_sheets_uuid = get_request_parameter(
        "google_sheets_uuid", request, json=True, required=True
    )
    phantom_name = get_request_parameter(
        "phantom_name", request, json=True, required=True
    )
    phantom_uuid = get_request_parameter(
        "phantom_uuid", request, json=True, required=True
    )

    resp = create_phantom_buster_config(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        google_sheets_uuid=google_sheets_uuid,
        phantom_type=PhantomBusterType.OUTBOUND_ENGINE,
        phantom_name=phantom_name,
        phantom_uuid=phantom_uuid,
    )

    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/create/inbox_scraper_config", methods=["POST"])
def post_inbox_scraper_config():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    phantom_name = get_request_parameter(
        "phantom_name", request, json=True, required=True
    )
    phantom_uuid = get_request_parameter(
        "phantom_uuid", request, json=True, required=True
    )

    resp = create_phantom_buster_config(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        phantom_type=PhantomBusterType.INBOX_SCRAPER,
        phantom_name=phantom_name,
        phantom_uuid=phantom_uuid,
    )

    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/get-all-phantom-busters", methods=["GET"])
def get_all_phantom_busters_endpoint():
    resp = get_all_phantom_busters()
    return jsonify(resp)
