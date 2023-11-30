from flask import Blueprint, jsonify, request
from src.utils.request_helpers import get_request_parameter

from src.weekly_report.services import (
    generate_weekly_report_data_payload,
    send_all_emails,
    send_email_with_data,
)

WEEKLY_REPORT_BLUEPRINT = Blueprint("weekly_report", __name__)

# TODO: Create a weekly report for @Aakash
# 1. Get all the data together
# 2. Insert into template
# 3. Send template in test mode
# 4. Send template in production mode


@WEEKLY_REPORT_BLUEPRINT.route("/<client_sdr_id>/send", methods=["POST"])
def index(client_sdr_id: int):
    success = send_email_with_data(client_sdr_id=client_sdr_id)

    if success:
        return jsonify({"message": "Email sent successfully!"}), 200

    return jsonify({"message": "Email failed to send!"}), 500


@WEEKLY_REPORT_BLUEPRINT.route("/send_all_emails_test_mode", methods=["POST"])
def send_all_emails_test_mode():
    to_emails = get_request_parameter("to_emails", request, json=True, required=True)

    success = send_all_emails(test_mode=True, to_emails=to_emails)

    if success:
        return jsonify({"message": "Email sent successfully!"}), 200

    return jsonify({"message": "Email failed to send!"}), 500
