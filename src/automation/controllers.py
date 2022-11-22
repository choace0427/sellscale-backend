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
from src.automation.inbox_scraper import scrape_inbox
from src.automation.services import create_new_auto_connect_phantom

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
    resp = get_all_phantom_busters(
        pb_type=PhantomBusterType.OUTBOUND_ENGINE, search_term="Auto Connect"
    )
    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/get-all-inbox-scrapers", methods=["GET"])
def get_all_inbox_scrapers_endpoint():
    resp = get_all_phantom_busters(
        pb_type=PhantomBusterType.INBOX_SCRAPER, search_term="Inbox Scraper"
    )
    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/scrape_inbox", methods=["GET"])
def scrape_inbox_from_client_sdr_id():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=False, required=True
    )
    resp = scrape_inbox(client_sdr_id=client_sdr_id)
    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/configure_phantom_agents", methods=["POST"])
def configure_phantom_agents():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    linkedin_session_cookie = get_request_parameter(
        "linkedin_session_cookie", request, json=True, required=True
    )
    google_sheet_uuid = get_request_parameter(
        "google_sheet_uuid", request, json=True, required=True
    )

    inbox_scraper_pb_config, auto_connect_pb_config = create_new_auto_connect_phantom(
        client_sdr_id=client_sdr_id,
        linkedin_session_cookie=linkedin_session_cookie,
        google_sheet_uuid=google_sheet_uuid,
    )

    return jsonify(
        {
            "inbox_scraper_pb_config": inbox_scraper_pb_config,
            "auto_connect_pb_config": auto_connect_pb_config,
        }
    )
