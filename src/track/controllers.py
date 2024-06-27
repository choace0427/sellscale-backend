from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.track.services import create_track_event, get_client_track_source_metadata, get_most_recent_track_event, get_website_tracking_script, verify_track_source
from src.track.services import find_company_from_orginfo

from src.utils.request_helpers import get_request_parameter

TRACK_BLUEPRINT = Blueprint("track", __name__)


@TRACK_BLUEPRINT.route("/webpage", methods=["POST"])
def create():
    ip = get_request_parameter("ip", request, json=True, required=True)
    page = get_request_parameter("page", request, json=True, required=True)
    track_key = get_request_parameter("track_key", request, json=True, required=True)

    success = create_track_event(ip=ip, page=page, track_key=track_key)

    if not success:
        return "ERROR", 400
    return "OK", 200

@TRACK_BLUEPRINT.route("/get_script", methods=["GET"])
@require_user
def get_script(client_sdr_id: int):
    script = get_website_tracking_script(client_sdr_id)
    return jsonify({
        "script": script
    }), 200

@TRACK_BLUEPRINT.route("/verify_source", methods=["GET"])
@require_user
def verify_source(client_sdr_id: int):
    success, msg = verify_track_source(client_sdr_id)
    if not success:
        return msg, 400
    return msg, 200

@TRACK_BLUEPRINT.route("/most_recent_track_event", methods=["GET"])
@require_user
def most_recent_track_event(client_sdr_id: int):
    event = get_most_recent_track_event(client_sdr_id)
    return jsonify(event.to_dict()), 200

@TRACK_BLUEPRINT.route("/track_source_metadata", methods=["GET"])
@require_user
def track_source_metadata(client_sdr_id: int):
    metadata = get_client_track_source_metadata(client_sdr_id)
    return jsonify(metadata), 200