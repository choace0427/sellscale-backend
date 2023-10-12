from app import db, app

from flask import Blueprint, request, jsonify
from src.email_scheduling.services import get_email_messaging_schedule_entries
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user


EMAIL_SCHEDULING_BLUEPRINT = Blueprint("email/schedule", __name__)


@EMAIL_SCHEDULING_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_email_messaging_schedule_entries_endpoint(client_sdr_id: int):
    """Gets all email messaging schedule entries for a given client SDR ID."""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=False, parameter_type=int
    )
    future_only = get_request_parameter(
        "future_only", request, json=False, required=False, parameter_type=bool
    )

    if future_only and type(future_only) == str:
        future_only = future_only.lower() == "true"

    schedule = get_email_messaging_schedule_entries(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        future_only=future_only
    )

    return jsonify({"status": "success", "data": {"schedule": schedule}}), 200
