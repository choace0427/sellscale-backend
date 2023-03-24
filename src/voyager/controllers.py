from flask import Blueprint, jsonify, request
from src.voyager.services import update_conversation_entries
from src.voyager.services import update_linked_cookies
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.voyager.linkedin import Linkedin

VOYAGER_BLUEPRINT = Blueprint("voyager", __name__)

@VOYAGER_BLUEPRINT.route("/send_message", methods=["POST"])
@require_user
def send_message(client_sdr_id: int):
    """Sends a LinkedIn message to a prospect"""

    public_id = get_request_parameter("public_id", request, json=True, required=True)
    msg = get_request_parameter("message", request, json=True, required=True)

    api = Linkedin(client_sdr_id)
    api.send_message(msg, recipients=[api.get_urn_id_from_public_id(public_id)])

    return jsonify({"message": "Sent message"}), 200


@VOYAGER_BLUEPRINT.route("/conversation", methods=["GET"])
@require_user
def get_conversation(client_sdr_id: int):
    """Gets a conversation with a prospect"""

    public_id = get_request_parameter("public_id", request, json=False, required=True)

    api = Linkedin(client_sdr_id)

    details = api.get_conversation_details(api.get_urn_id_from_public_id(public_id))
    convo = api.get_conversation(details['entityUrn'].replace('urn:li:fs_conversation:', ''))

    return jsonify({"message": "Success", "data": convo}), 200


@VOYAGER_BLUEPRINT.route("/recent_conversations", methods=["GET"])
@require_user
def get_recent_conversations(client_sdr_id: int):
    """Gets recent conversation data with filters"""

    timestamp = get_request_parameter("timestamp", request, json=False, required=False)
    read = get_request_parameter("read", request, json=False, required=False)
    starred = get_request_parameter("starred", request, json=False, required=False)
    with_connection = get_request_parameter("with_connection", request, json=False, required=False)

    api = Linkedin(client_sdr_id)

    data = api.get_conversations()
    convos = data['elements']

    if timestamp:
      convos = filter(lambda x: x['lastActivityAt'] > int(timestamp), convos)
    if read:
      convos = filter(lambda x: x['read'] == bool(read), convos)
    if starred:
      convos = filter(lambda x: x['starred'] == bool(starred), convos)
    if with_connection:
      convos = filter(lambda x: x['withNonConnection'] != bool(with_connection), convos)

    return jsonify({"message": "Success", "data": list(convos)}), 200


@VOYAGER_BLUEPRINT.route("/auth_tokens", methods=["POST"])
@require_user
def update_auth_tokens(client_sdr_id: int):
    """Updates the LinkedIn auth tokens for a SDR"""

    cookies = get_request_parameter("cookies", request, json=True, required=True, parameter_type=str)

    status_text, status = update_linked_cookies(client_sdr_id, cookies)

    return jsonify({"message": status_text}), status


@VOYAGER_BLUEPRINT.route("/update_conversation_entries", methods=["POST"])
@require_user
def update_li_conversation_entries(client_sdr_id: int):
    """Updates the LinkedIn auth tokens for a SDR"""

    public_id = get_request_parameter("public_id", request, json=False, required=True)

    update_conversation_entries(client_sdr_id, public_id)

    return jsonify({"message": 'Updated conversation'}), 200
