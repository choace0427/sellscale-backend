from flask import Blueprint, jsonify, request
from src.task_report.services import send_task_report_email
from src.utils.request_helpers import get_request_parameter
from src.task_report.services import send_all_pending_task_report_emails

TASK_REPORT_BLUEPRINT = Blueprint("task_report", __name__)


@TASK_REPORT_BLUEPRINT.route("/<client_sdr_id>/send", methods=["POST"])
def index(client_sdr_id: int):
    to_emails = get_request_parameter("to_emails", request, json=True, required=True)
    success = send_task_report_email(client_sdr_id=client_sdr_id)

    if success:
        return jsonify({"message": "Email sent successfully!"}), 200

    return jsonify({"message": "Email failed to send!"}), 500
