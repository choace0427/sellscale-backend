
from crypt import methods
from flask import Blueprint, request, jsonify
from src.calendly.services import update_calendly_access_token
from src.prospecting.models import Prospect
from app import db
import os
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter

CALENDLY_BLUEPRINT = Blueprint("calendly", __name__)


@CALENDLY_BLUEPRINT.route("/access_token", methods=["POST"])
@require_user
def post_access_token_from_code(client_sdr_id: int):
    
    code = get_request_parameter(
        "code", request, json=True, required=False, parameter_type=str
    )
    refresh_token = get_request_parameter(
        "refresh_token", request, json=True, required=False, parameter_type=str
    )
    if not code and not refresh_token:
        return jsonify({"message": "Missing code or refresh_token"}), 400

    success = update_calendly_access_token(client_sdr_id, code, refresh_token)

    if not success:
        return jsonify({"message": "Failed to update access token"}), 400
    
    return jsonify({"message": "Success"}), 200
