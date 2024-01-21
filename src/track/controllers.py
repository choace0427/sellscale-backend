from flask import Blueprint, request
from src.track.services import create_track_event
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
