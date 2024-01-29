from app import slack_app_handler
from flask import Blueprint, request, jsonify

from src.utils.request_helpers import get_request_parameter
from src.utils.slack import URL_MAP, send_slack_message


SLACK_EVENTS_BLUEPRINT = Blueprint("slack/events", __name__)


@SLACK_EVENTS_BLUEPRINT.route("/", methods=["POST"])
def slack_events():
    payload = get_request_parameter("payload", request, json=True, required=True)

    type = payload.get("type", "")

    send_slack_message(
        message=f"SLACKBOT: Received interaction of type {type}. Full payload: {payload}",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    slack_app_handler.handle(request)

    return jsonify({"status": "success"}), 200
