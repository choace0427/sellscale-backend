from app import db, app

from flask import Blueprint, request, jsonify
from src.authentication.decorators import require_user
from src.email_warmup.services import pass_through_smartlead_warmup_request


EMAIL_WARMUP_BLUEPRINT = Blueprint("email/warmup", __name__)


@EMAIL_WARMUP_BLUEPRINT.route("/smartlead", methods=["GET"])
@require_user
def get_smartlead_warmup_passthrough_api(client_sdr_id: int):
    """Passes through the Smartlead warmup API."""

    results = pass_through_smartlead_warmup_request(client_sdr_id=client_sdr_id)

    return jsonify({'status': 'success', 'inboxes': results}), 200
