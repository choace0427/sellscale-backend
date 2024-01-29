from app import slack_app_handler
from flask import Blueprint, request, jsonify

from src.utils.request_helpers import get_request_parameter
from src.utils.slack import URL_MAP, send_slack_message


SLACK_EVENTS_BLUEPRINT = Blueprint("slack/events", __name__)


@SLACK_EVENTS_BLUEPRINT.route("/", methods=["POST"])
def slack_events():
    """Handle Slack events"""
    event_type = get_request_parameter("type", request, required=True)

    # If the event type is a URL verification, return the challenge
    if event_type == "url_verification":
        return jsonify({"challenge": request.json["challenge"]}), 200

    send_slack_message(
        message=f"SLACKBOT: Received interaction of type {event_type}. Full payload: {request.json}",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    slack_app_handler.handle(request)

    return jsonify({"status": "success"}), 200
