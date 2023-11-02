from app import db

from flask import Blueprint, request, jsonify
from src.authentication.decorators import require_user
from src.channel_warmup.services import pass_through_smartlead_warmup_request


CHANNEL_WARMUP = Blueprint("email/warmup", __name__)


@CHANNEL_WARMUP.route("/smartlead", methods=["GET"])
@require_user
def get_smartlead_warmup_passthrough_api(client_sdr_id: int):
    """Passes through the Smartlead warmup API."""

    results = pass_through_smartlead_warmup_request(client_sdr_id=client_sdr_id)

    return jsonify({"status": "success", "inboxes": results}), 200
