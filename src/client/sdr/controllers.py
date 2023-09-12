from app import db
from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.client.sdr.services_client_sdr import create_sla_schedule, get_sla_schedules_for_sdr, update_sla_schedule
from src.utils.datetime.dateparse_utils import convert_string_to_datetime
from src.utils.request_helpers import get_request_parameter

CLIENT_SDR_BLUEPRINT = Blueprint("client/sdr", __name__)


@CLIENT_SDR_BLUEPRINT.route("/sla/schedule", methods=["GET"])
@require_user
def get_sla_schedule(client_sdr_id: int):
    start_date = get_request_parameter(
        "start_date", request, json=False, required=False, parameter_type=str
    )
    end_date = get_request_parameter(
        "end_date", request, json=False, required=False, parameter_type=str
    )

    start_date = convert_string_to_datetime(start_date) if start_date else None
    end_date = convert_string_to_datetime(end_date) if end_date else None

    schedules = get_sla_schedules_for_sdr(
        client_sdr_id=client_sdr_id,
        start_date=start_date,
        end_date=end_date
    )

    return jsonify({"status": "success", "data": {"schedules": schedules}}), 200


@CLIENT_SDR_BLUEPRINT.route("/sla/schedule", methods=["PATCH"])
@require_user
def patch_sla_schedule(client_sdr_id: int):
    sla_schedule_id = get_request_parameter(
        "sla_schedule_id", request, json=True, required=False, parameter_type=int
    )
    start_date = get_request_parameter(
        "start_date", request, json=True, required=False, parameter_type=str
    )
    if not sla_schedule_id and not start_date:
        return jsonify({"status": "error", "message": "Schedule ID or Start Date must be included"}), 400

    linkedin_volume = get_request_parameter(
        "linkedin_volume", request, json=True, required=False, parameter_type=int
    )
    linkedin_special_notes = get_request_parameter(
        "linkedin_special_notes", request, json=True, required=False, parameter_type=str
    )
    email_volume = get_request_parameter(
        "email_volume", request, json=True, required=False, parameter_type=int
    )
    email_special_notes = get_request_parameter(
        "email_special_notes", request, json=True, required=False, parameter_type=str
    )

    start_date = convert_string_to_datetime(start_date) if start_date else None

    success, message = update_sla_schedule(
        client_sdr_id=client_sdr_id,
        sla_schedule_id=sla_schedule_id,
        start_date=start_date,
        linkedin_volume=linkedin_volume,
        linkedin_special_notes=linkedin_special_notes,
        email_volume=email_volume,
        email_special_notes=email_special_notes
    )

    if not success:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success", "data": {}}), 200


@CLIENT_SDR_BLUEPRINT.route("/sla/schedule", methods=["POST"])
@require_user
def post_sla_schedule(client_sdr_id: int):
    start_date = get_request_parameter(
        "start_date", request, json=True, required=True, parameter_type=str
    )
    end_date = get_request_parameter(
        "end_date", request, json=True, required=False, parameter_type=str
    )
    linkedin_volume = get_request_parameter(
        "linkedin_volume", request, json=True, required=False, parameter_type=int
    )
    linkedin_special_notes = get_request_parameter(
        "linkedin_special_notes", request, json=True, required=False, parameter_type=str
    )
    email_volume = get_request_parameter(
        "email_volume", request, json=True, required=False, parameter_type=int
    )
    email_special_notes = get_request_parameter(
        "email_special_notes", request, json=True, required=False, parameter_type=str
    )

    start_date = convert_string_to_datetime(start_date) if start_date else None
    end_date = convert_string_to_datetime(end_date) if end_date else None

    schedule_id = create_sla_schedule(
        client_sdr_id=client_sdr_id,
        start_date=start_date,
        end_date=end_date,
        linkedin_volume=linkedin_volume,
        linkedin_special_notes=linkedin_special_notes,
        email_volume=email_volume,
        email_special_notes=email_special_notes
    )

    return jsonify({"status": "success", "data": {"schedule_id": schedule_id}}), 200
