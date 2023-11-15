from typing import List
from flask import Blueprint, request, jsonify
from src.smartlead.services import get_email_warmings_for_sdr
from app import db
import os
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter

SMARTLEAD_BLUEPRINT = Blueprint("smart_email", __name__)

@SMARTLEAD_BLUEPRINT.route("/email_warmings", methods=["GET"])
@require_user
def get_email_warmings(client_sdr_id: int):

    email_warmings = get_email_warmings_for_sdr(client_sdr_id)

    return jsonify({"message": "Success", "data": [warming.to_dict() for warming in email_warmings]}), 200
