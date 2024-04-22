from functools import wraps
import json
import os
from flask import Blueprint, jsonify, request

from src.merge_crm.webhooks.opportunity_updated import (
    create_and_process_crm_opportunity_updated_payload,
)


MERGE_CRM_WEBHOOKS_BLUEPRINT = Blueprint("merge/crm/webhooks", __name__)


def authenticate_webhook(f) -> None:
    """Decorator to authenticate Merge CRM webhooks.

    Args:
        f (function): The function to be decorated.

    Returns:
        None
    """
    import base64
    import hashlib
    import hmac

    @wraps(f)
    def decorator(*args, **kwargs):
        signature = os.environ.get("MERGE_API_WEBHOOK_SECRET")
        request_body: dict = request.get_json()
        request_body_str: str = json.dumps(request_body)

        hmac_digest = hmac.new(
            signature.encode("utf-8"),
            request_body_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        b64_encoded = base64.urlsafe_b64encode(hmac_digest).decode()

        signature_matches = b64_encoded == request.headers["X-Merge-Webhook-Signature"]
        if not signature_matches:
            return jsonify({"status": "error", "message": "Invalid signature."}), 401

        return f(*args, **kwargs)

    return decorator


@MERGE_CRM_WEBHOOKS_BLUEPRINT.route("/opportunity/updated", methods=["POST"])
@authenticate_webhook
def account_updated():
    """Webhook for Merge CRM opportunity updated event."""
    payload = request.get_json()
    success = create_and_process_crm_opportunity_updated_payload(payload=payload)
    if not success:
        return (
            jsonify({"status": "error", "message": "Failed to process payload."}),
            500,
        )

    return (
        jsonify({"status": "success", "message": "Payload processed successfully."}),
        200,
    )
