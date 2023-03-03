import json
from flask import Blueprint, request, jsonify
from flask_csv import send_csv
from model_import import Prospect
from datetime import datetime, timedelta
from model_import import ClientSDR
from src.li_conversation.services import (
    update_linkedin_conversation_entries,
    update_li_conversation_extractor_phantom,
    generate_chat_gpt_response_to_conversation_thread,
)
from src.utils.request_helpers import get_request_parameter


LI_CONVERSATION_SCRAPE_INTERVAL = 2
LI_CONVERASTION_BLUEPRINT = Blueprint("li_conversation", __name__)


@LI_CONVERASTION_BLUEPRINT.route(
    "/update_linkedin_conversation_entries", methods=["POST"]
)
def post_update_linkedin_conversation_entries():
    update_linkedin_conversation_entries()
    return "OK", 200


@LI_CONVERASTION_BLUEPRINT.route("/<client_sdr_id>")
def get_li_conversation_csv(client_sdr_id):
    """Returns a CSV of prospects who have had a LinkedIn conversation extracted in the last 24 hours."""
    prospects = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.li_last_message_timestamp
        > datetime.now() - timedelta(days=LI_CONVERSATION_SCRAPE_INTERVAL),
    ).all()

    linkedin_urls = [
        {"linkedin_url": "https://www." + prospect.linkedin_url}
        for prospect in prospects
        if prospect.linkedin_url
    ]

    return send_csv(
        linkedin_urls,
        "test.csv",
        ["linkedin_url"],
    )


@LI_CONVERASTION_BLUEPRINT.route("/sdr/<client_sdr_id>", methods=["POST"])
def post_client_sdr_li_conversation_arguments(client_sdr_id):
    """Saves the LinkedIn conversation arguments for a given SDR."""
    message, status_code = update_li_conversation_extractor_phantom(client_sdr_id)

    return message, status_code


@LI_CONVERASTION_BLUEPRINT.route("/prospect/generate_response", methods=["POST"])
def get_prospect_li_conversation():
    """Returns a prospect's LinkedIn conversation data."""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    conversation_url = prospect.li_conversation_thread_id
    if not conversation_url:
        return "No conversation thread found.", 404

    response = generate_chat_gpt_response_to_conversation_thread(conversation_url)
    if response:
        return jsonify({"message": response}), 200
    else:
        return "No conversation thread found.", 404
