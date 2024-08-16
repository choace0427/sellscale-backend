from flask import Blueprint, request

from src.utils.request_helpers import get_request_parameter
from src.utils.slack import URL_MAP, send_slack_message

from .services import get_echo

ECHO_BLUEPRINT = Blueprint("echo", __name__)


@ECHO_BLUEPRINT.route("/")
def index():
    get_echo()
    return "OK", 200

@ECHO_BLUEPRINT.route("/send-slack-message", methods=["POST"])
def post_send_slack_message():
    message = get_request_parameter(
        "message", request, json=True, required=True
    )
    webhook_key = get_request_parameter(
        "webhook_key", request, json=True, required=True
    )
    send_slack_message(
        message=message,
        webhook_urls=[URL_MAP[webhook_key]],
    )

    return "OK", 200