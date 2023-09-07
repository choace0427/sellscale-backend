
from app import db
from flask import Blueprint, request, jsonify
from model_import import ClientSDR, Client
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user
from src.utils.slack import send_slack_message
from src.utils.slack import URL_MAP

INTEGRATION_BLUEPRINT = Blueprint("integration", __name__)


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
            password=password,
        ),
        webhook_urls=[URL_MAP["linkedin-credentials"]],
    )

    return jsonify({"message": "Sent credentials"}), 200


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
            cookie=cookie,
        ),
        webhook_urls=[URL_MAP["linkedin-credentials"]],
    )

    return jsonify({"message": "Sent cookie"}), 200
