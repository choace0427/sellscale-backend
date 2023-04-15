from src.client.models import ClientArchetype
from app import db

from flask import Blueprint, request, jsonify
from model_import import ClientSDR, Client
from src.utils.request_helpers import get_request_parameter
from src.integrations.vessel import SalesEngagementIntegration
import os
import requests
from src.authentication.decorators import require_user
from src.utils.slack import send_slack_message
from src.utils.slack import URL_MAP

INTEGRATION_BLUEPRINT = Blueprint("integration", __name__)


@INTEGRATION_BLUEPRINT.route("/mailboxes", methods=["GET"])
def get_mailbox_by_email():
    email = get_request_parameter("email", request, json=False, required=True)
    client_id = get_request_parameter("client_id", request, json=False, required=True)

    integration = SalesEngagementIntegration(
        client_id=int(client_id),
    )
    options = integration.find_mailbox_autofill_by_email(email=email)
    return jsonify({"mailbox_options": options})


@INTEGRATION_BLUEPRINT.route("/set-persona-sequence", methods=["POST"])
@require_user
def post_set_persona_sequence(client_sdr_id: int):
    
    #TODO: Confirm that the user has access to this persona

    persona_id = get_request_parameter("persona_id", request, json=True, required=True, parameter_type=int)
    sequence_id = get_request_parameter("sequence_id", request, json=True, required=True, parameter_type=int)
    if sequence_id == -1: sequence_id = None

    client_archetype = ClientArchetype.query.get(persona_id)
    if not client_archetype:
      return jsonify({"message": 'Persona not found'}), 404
    
    client_archetype.vessel_sequence_id = sequence_id
    db.session.add(client_archetype)
    db.session.commit()

    return jsonify({"message": 'Set sequence'}), 200


@INTEGRATION_BLUEPRINT.route("/sequences-auth", methods=["GET"])
@require_user
def get_all_sequences(client_sdr_id: int):

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    try:
        integration = SalesEngagementIntegration(
            client_id=int(client_sdr.client_id),
        )
        options = integration.find_all_sequences()
        return jsonify({"sequence_options": options})
    except Exception as e:
        return jsonify({"message": 'No vessel access token'}), 200


@INTEGRATION_BLUEPRINT.route("/sequences", methods=["GET"])
def get_sequences_by_name():
    name = get_request_parameter("name", request, json=False, required=True)
    client_id = get_request_parameter("client_id", request, json=False, required=True)

    try:
        integration = SalesEngagementIntegration(
            client_id=int(client_id),
        )
        options = integration.find_sequence_autofill_by_name(name=name)
        return jsonify({"sequence_options": options})
    except Exception as e:
        return jsonify({"message": 'No vessel access token'}), 200


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
    if 'connectionId' in data:
        connection_id = data["connectionId"]
        access_token = data["accessToken"]

        client.vessel_access_token = access_token
        client.vessel_sales_engagement_connection_id = connection_id
        db.session.add(client)
        db.session.commit()

        return 'OK', 200

    return jsonify(data)

@INTEGRATION_BLUEPRINT.route("/vessel/sales-engagement-connection")
@require_user
def get_vessel_sales_engagement_connection(client_sdr_id: int):
    client_sdr = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client: Client = Client.query.get(client_id)
    connected = False
    if client and client.vessel_access_token:
        connected = True
    return jsonify({'connected': connected})


@INTEGRATION_BLUEPRINT.route("/linkedin/send-credentials", methods=["POST"])
@require_user
def post_linkedin_credentials(client_sdr_id: int):
    username = get_request_parameter("username", request, json=True, required=True)
    password = get_request_parameter("password", request, json=True, required=True)

    client_sdr = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client: Client = Client.query.get(client_id)

    send_slack_message(
        message="*New Credentials Submit*\nFor {client_sdr_name} from {client_company} :tada:\n\n_Username:_ {username}\n_Password:_ {password}\n\n_Please delete this message once transferred to 1password._".format(
          client_sdr_name=client_sdr.name,
          client_company=client.company,
          username=username,
          password=password
        ),
        webhook_urls=[URL_MAP["linkedin-credentials"]],
    )

    return jsonify({"message": 'Sent credentials'}), 200


@INTEGRATION_BLUEPRINT.route("/linkedin/send-cookie", methods=["POST"])
@require_user
def post_linkedin_cookie(client_sdr_id: int):
    cookie = get_request_parameter("cookie", request, json=True, required=True)

    client_sdr = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client: Client = Client.query.get(client_id)

    send_slack_message(
        message="*New Cookie Submit*\nFor {client_sdr_name} from {client_company} :tada:\n\n_Cookie:_ {cookie}\n\n_Please delete this message once transferred to 1password._".format(
          client_sdr_name=client_sdr.name,
          client_company=client.company,
          cookie=cookie
        ),
        webhook_urls=[URL_MAP["linkedin-credentials"]],
    )

    return jsonify({"message": 'Sent cookie'}), 200


@INTEGRATION_BLUEPRINT.route("/outreach/send-sequence", methods=["POST"])
@require_user
def post_outreach_sequence(client_sdr_id: int):

    return jsonify({"message": 'Deprecated.'}), 204
