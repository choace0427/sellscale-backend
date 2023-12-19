from flask import Blueprint, request, jsonify
from src.smartlead.webhooks.email_bounced import create_and_process_email_bounce_payload
from src.smartlead.webhooks.email_opened import create_and_process_email_opened_payload

from src.smartlead.webhooks.email_sent import create_and_process_email_sent_payload


SMARTLEAD_WEBHOOKS_BLUEPRINT = Blueprint("smartlead/webhooks", __name__)


@SMARTLEAD_WEBHOOKS_BLUEPRINT.route("/email_sent", methods=["POST"])
def smartlead_webhook_email_sent():
    """Webhook for Smartlead email sent event."""
    payload = request.get_json()

    success = create_and_process_email_sent_payload(payload=payload)
    if not success:
        return (
            jsonify(
                {"status": "error", "message": "Failed to process webhook payload"}
            ),
            500,
        )

    return jsonify({"status": "success", "data": {}}), 200


@SMARTLEAD_WEBHOOKS_BLUEPRINT.route("/email_opened", methods=["POST"])
def smartlead_webhook_email_opened():
    """Webhook for Smartlead email opened event."""
    payload = request.get_json()

    success = create_and_process_email_opened_payload(payload=payload)
    if not success:
        return (
            jsonify(
                {"status": "error", "message": "Failed to process webhook payload"}
            ),
            500,
        )

    return jsonify({"status": "success", "data": {}}), 200


@SMARTLEAD_WEBHOOKS_BLUEPRINT.route("/email_bounced", methods=["POST"])
def smartlead_webhook_email_bounced():
    """Webhook for Smartlead email bounced event."""
    payload = request.get_json()

    success = create_and_process_email_bounce_payload(payload=payload)
    if not success:
        return (
            jsonify(
                {"status": "error", "message": "Failed to process webhook payload"}
            ),
            500,
        )

    return jsonify({"status": "success", "data": {}}), 200
