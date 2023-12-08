import datetime
from flask import Blueprint, jsonify, request
from src.triggers.services import createTrigger, runTrigger
from src.authentication.decorators import require_user
from src.triggers.models import (
    Trigger,
    TriggerProspect,
    TriggerRun,
    convertBlocksToDict,
    get_blocks_from_output_dict,
)
from app import db
from src.utils.request_helpers import get_request_parameter

SOCKETS_BLUEPRINT = Blueprint("sockets", __name__)


@SOCKETS_BLUEPRINT.route("/receive-message", methods=["POST"])
# @require_user TODO: Add authentication
def post_receive_message():
    data = get_request_parameter("data", request, json=True, required=True)

    sdr_id = data.get("sdr_id")
    payload = data.get("payload")

    print("sdr_id", sdr_id)
    print("payload", payload)

    return jsonify({"message": "Success", "data": None}), 200
