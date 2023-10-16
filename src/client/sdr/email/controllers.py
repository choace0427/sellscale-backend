from datetime import datetime
from app import db
from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.client.sdr.email.models import EmailType, SDREmailBank
from src.client.sdr.email.services_email_bank import create_sdr_email_bank, get_sdr_email_banks, update_sdr_email_bank
from src.client.sdr.email.services_email_schedule import update_sdr_email_send_schedule
from src.utils.request_helpers import get_request_parameter


SDR_EMAIL_BLUEPRINT = Blueprint("client/sdr/email", __name__)


@SDR_EMAIL_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_sdr_email_banks_endpoint(client_sdr_id: int):
    """Endpoint to get SDR Email Banks"""
    active_only = get_request_parameter(
        "active_only", request, json=True, parameter_type=bool)
    if active_only and type(active_only) == str:
        active_only = active_only.lower() == "true"

    email_banks: list[SDREmailBank] = get_sdr_email_banks(
        client_sdr_id=client_sdr_id,
        active_only=active_only
    )

    email_banks_dict = [email_bank.to_dict() for email_bank in email_banks]

    return jsonify({"status": "success", "data": {"emails": email_banks_dict}}), 200


@SDR_EMAIL_BLUEPRINT.route("/", methods=["POST"])
@require_user
def post_create_sdr_email_bank(client_sdr_id: int):
    """Endpoint to create an SDR Email Bank"""
    email_address = get_request_parameter(
        "email_address", request, json=True, parameter_type=str)
    email_type = get_request_parameter(
        "email_type", request, json=True, parameter_type=str)


    if email_type and type(email_type) == str:
        if email_type.upper() not in ["ANCHOR", "SELLSCALE", "ALIAS"]:
            return jsonify({"status": "error", "message": "Invalid email type"}), 400
        else:
            email_type = EmailType.__members__[email_type.upper()]

    success, message = create_sdr_email_bank(
        client_sdr_id=client_sdr_id,
        email_address=email_address,
        email_type=email_type
    )

    if not success:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success"}), 200


@SDR_EMAIL_BLUEPRINT.route("/<int:email_bank_id>", methods=["PATCH"])
@require_user
def patch_sdr_email_bank(client_sdr_id: int, email_bank_id: int):
    """Endpoint to update an SDR Email Bank"""
    active = get_request_parameter(
        "active", request, json=True, parameter_type=bool)
    email_type = get_request_parameter(
        "email_type", request, json=True, parameter_type=str)

    if email_type and type(email_type) == str:
        if email_type.upper() not in ["ANCHOR", "SELLSCALE", "ALIAS"]:
            return jsonify({"status": "error", "message": "Invalid email type"}), 400
        else:
            email_type = EmailType.__members__[email_type.upper()]

    success, message = update_sdr_email_bank(
        email_bank_id=email_bank_id,
        active=active,
        email_type=email_type
    )

    if not success:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success"}), 200


@SDR_EMAIL_BLUEPRINT.route("/<int:email_bank_id>/schedule", methods=["PATCH"])
@require_user
def patch_email_bank_send_schedule(client_sdr_id: int, email_bank_id: int):
    """Endpoint to update an SDR Email Bank Send Schedule"""
    time_zone = get_request_parameter(
        "time_zone", request, json=True, parameter_type=str)
    days = get_request_parameter(
        "days", request, json=True, parameter_type=list)
    start_time = get_request_parameter(
        "start_time", request, json=True, parameter_type=str)
    end_time = get_request_parameter(
        "end_time", request, json=True, parameter_type=str)

    if start_time and type(start_time) == str:
        start_time = datetime.strptime(start_time, "%H:%M").time()
    if end_time and type(end_time) == str:
        end_time = datetime.strptime(end_time, "%H:%M").time()

    success = update_sdr_email_send_schedule(
        client_sdr_id=client_sdr_id,
        email_bank_id=email_bank_id,
        time_zone=time_zone,
        days=days,
        start_time=start_time,
        end_time=end_time
    )

    if not success:
        return jsonify({"status": "error", "message": "Could not update inbox send schedule."}), 400

    return jsonify({"status": "success"}), 200



@SDR_EMAIL_BLUEPRINT.route("/schedule", methods=["PATCH"])
@require_user
def patch_sdr_email_send_schedule(client_sdr_id: int):
    """Endpoint to update an SDR Email Send Schedule, applies universally"""
    time_zone = get_request_parameter(
        "time_zone", request, json=True, parameter_type=str)
    days = get_request_parameter(
        "days", request, json=True, parameter_type=list)
    start_time = get_request_parameter(
        "start_time", request, json=True, parameter_type=str)
    end_time = get_request_parameter(
        "end_time", request, json=True, parameter_type=str)

    if start_time and type(start_time) == str:
        start_time = datetime.strptime(start_time, "%H:%M").time()
    if end_time and type(end_time) == str:
        end_time = datetime.strptime(end_time, "%H:%M").time()

    success = update_sdr_email_send_schedule(
        client_sdr_id=client_sdr_id,
        time_zone=time_zone,
        days=days,
        start_time=start_time,
        end_time=end_time
    )

    if not success:
        return jsonify({"status": "error", "message": "Could not update inbox send schedule."}), 400

    return jsonify({"status": "success"}), 200