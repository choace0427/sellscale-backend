from app import db

from flask import Blueprint, request, jsonify
from src.utils.request_helpers import get_request_parameter
from src.integrations.vessel import SalesEngagementIntegration

INTEGRATION_BLUEPRINT = Blueprint("integration", __name__)


@INTEGRATION_BLUEPRINT.route("/mailboxes", methods=["GET"])
def get_mailbox_by_email():
    email = get_request_parameter("name", request, json=True, required=True)
    client_id = get_request_parameter("client_id", request, json=True, required=True)

    integration = SalesEngagementIntegration(
        client_id=client_id,
    )
    options = integration.find_mailbox_autofill_by_email(email=email)
    return jsonify({"mailbox_options": options})


@INTEGRATION_BLUEPRINT.route("/sequences", methods=["GET"])
def get_sequences_by_name():
    name = get_request_parameter("name", request, json=True, required=True)
    client_id = get_request_parameter("client_id", request, required=True)

    integration = SalesEngagementIntegration(
        client_id=client_id,
    )
    options = integration.find_sequence_autofill_by_name(name=name)
    return jsonify({"sequence_options": options})
