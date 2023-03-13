from app import db

from flask import Blueprint, request, jsonify
from model_import import ClientSDR, Client
from src.utils.request_helpers import get_request_parameter
from src.integrations.vessel import SalesEngagementIntegration
import os
import requests
from src.authentication.decorators import require_user


INTEGRATION_BLUEPRINT = Blueprint("integration", __name__)


@INTEGRATION_BLUEPRINT.route("/mailboxes", methods=["GET"])
def get_mailbox_by_email():
    email = get_request_parameter("email", request, json=False, required=True)
    client_id = get_request_parameter("client_id", request, json=False, required=True)

    integration = SalesEngagementIntegration(
        client_id=client_id,
    )
    options = integration.find_mailbox_autofill_by_email(email=email)
    return jsonify({"mailbox_options": options})


@INTEGRATION_BLUEPRINT.route("/sequences", methods=["GET"])
def get_sequences_by_name():
    name = get_request_parameter("name", request, json=False, required=True)
    client_id = get_request_parameter("client_id", request, json=False, required=True)

    integration = SalesEngagementIntegration(
        client_id=client_id,
    )
    options = integration.find_sequence_autofill_by_name(name=name)
    return jsonify({"sequence_options": options})


@INTEGRATION_BLUEPRINT.route("/vessel/link-token", methods=["POST"])
def post_vessel_link_token():
    headers = {"vessel-api-token": os.environ.get("VESSEL_API_KEY", "")}
    response = requests.post("https://api.vessel.land/link/token", headers=headers)
    body = response.json()
    return jsonify({"linkToken": body["linkToken"]})


@INTEGRATION_BLUEPRINT.route("/vessel/exchange-link-token", methods=['POST'])
@require_user
def post_vessel_exchange_link_token(client_sdr_id: int):
    public_token = get_request_parameter("publicToken", request, json=True, required=True)
    client_sdr = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client: Client = Client.query.get(client_id)
    headers = {
        "vessel-api-token": os.environ.get("VESSEL_API_KEY", "")
    }
    response = requests.post("https://api.vessel.land/link/exchange", json={
        "publicToken": public_token
    }, headers=headers)
    data = response.json()
    connection_id = data["connectionId"]
    access_token = data["accessToken"]

    client.vessel_access_token = access_token
    client.vessel_sales_engagement_connection_id = connection_id
    db.session.add(client)
    db.session.commit()

    return 'OK', 200
    