import json
from src.client.models import ClientSDR

from src.message_generation.services import get_li_convo_history
from app import db
from flask import Blueprint, request, jsonify
from src.utils.csv import send_csv
from model_import import Prospect, LinkedinConversationEntry
from datetime import datetime, timedelta
from src.bump_framework.models import BumpLength
from src.li_conversation.services import (
    generate_smart_response,
    update_linkedin_conversation_entries,
    update_li_conversation_extractor_phantom,
    generate_chat_gpt_response_to_conversation_thread,
    get_li_conversation_entries,
)
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user
from src.li_conversation.services import wizard_of_oz_send_li_message
from src.li_conversation.conversation_analyzer.analyzer import (
    run_all_conversation_analyzers,
)
from src.li_conversation.services_linkedin_initial_message_templates import (
    backfill_linkedin_initial_message_template_library_stats,
)

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
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.li_should_deep_scrape == True,
    ).all()

    updated_prospects = []
    linkedin_urls = []
    for prospect in prospects:
        prospect.li_should_deep_scrape = False
        updated_prospects.append(prospect)

        if prospect.linkedin_url:
            linkedin_urls.append(
                {"linkedin_url": "https://www." + prospect.linkedin_url}
            )

    db.session.bulk_save_objects(updated_prospects)
    db.session.commit()

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


@LI_CONVERASTION_BLUEPRINT.route("/prospect/generate_smart_response", methods=["POST"])
@require_user
def post_prospect_li_conversation_smart(client_sdr_id: int):
    """Generates a smart response using client, persona, and SDR brain"""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    additional_instructions = get_request_parameter(
        "additional_instructions", request, json=True, required=False
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.client_sdr_id != client_sdr_id:
        return jsonify({"error": "Unauthorized"}), 401

    response: str = generate_smart_response(prospect_id, additional_instructions)

    return jsonify({"message": response}), 200


@LI_CONVERASTION_BLUEPRINT.route("/prospect/generate_response", methods=["POST"])
def get_prospect_li_conversation():
    """Returns a prospect's LinkedIn conversation data."""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=False
    )
    account_research_copy = get_request_parameter(
        "account_research_copy", request, json=True, required=False
    )
    bump_length = get_request_parameter(
        "bump_length", request, json=True, required=False
    )

    override_bump_framework_template = get_request_parameter(
        "override_bump_framework_template", request, json=True, required=False
    )

    # Get the enum value for the bump length
    if bump_length is not None:
        found_key = False
        for key, val in BumpLength.__members__.items():
            if key == bump_length.upper():
                bump_length = val
                found_key = True
                break
        if not found_key:
            return jsonify({"error": "Invalid bump length."}), 400

    prospect: Prospect = Prospect.query.get(prospect_id)
    convo_history = get_li_convo_history(prospect.id)
    if not convo_history or len(convo_history) == 0:
        return jsonify({"error": "No conversation history found."}), 404

    response, prompt = generate_chat_gpt_response_to_conversation_thread(
        prospect_id=prospect.id,
        convo_history=convo_history,
        bump_framework_id=bump_framework_id,
        account_research_copy=account_research_copy,
        override_bump_length=bump_length,
        override_bump_framework_template=override_bump_framework_template,
    )  # type: ignore
    if response:
        return jsonify({"message": response, "prompt": prompt}), 200
    else:
        return jsonify({"error": "No conversation thread found."}), 404


@LI_CONVERASTION_BLUEPRINT.route("/prospect/send_woz_message", methods=["POST"])
@require_user
def post_prospect_li_conversation_woz(client_sdr_id: int):
    new_message = get_request_parameter(
        "new_message", request, json=True, required=True
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )

    message = wizard_of_oz_send_li_message(
        new_message=new_message, prospect_id=prospect_id, client_sdr_id=client_sdr_id
    )

    return jsonify({"message": message})


@LI_CONVERASTION_BLUEPRINT.route("/prospect/read_messages", methods=["POST"])
@require_user
def post_prospect_read_messages(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect and prospect.client_sdr_id != client_sdr_id:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        if not (client_sdr.role == 'ADMIN' and prospect.client_id == client_sdr.client_id):
            print(f"client_sdr_id: {client_sdr_id}, prospect.client_sdr_id: {prospect.client_sdr_id}", 'role:', client_sdr.role, 'client_id:', client_sdr.client_id, 'prospect.client_id:', prospect.client_id)
            return jsonify({"error": "This prospect does not belong to you"}), 403
        #override client_sdr_id to the one of the prospect because 
        #admins can read messages of any prospect of their client
        client_sdr_id = prospect.client_sdr_id

    updated = prospect.li_unread_messages != 0
    prospect.li_unread_messages = 0
    db.session.commit()

    return jsonify(
        {
            "message": "Success",
            "data": {
                "updated": updated,
            },
        }
    )


@LI_CONVERASTION_BLUEPRINT.route("/processed", methods=["POST"])
def post_prospect_li_conversation_processed():
    """Marks a prospect's LinkedIn conversation entry as processed."""
    li_conversation_id = get_request_parameter(
        "li_conversation_id", request, json=True, required=True, parameter_type=int
    )

    li_entry: LinkedinConversationEntry = LinkedinConversationEntry.query.get(
        li_conversation_id
    )
    li_entry.entry_processed_manually = True
    db.session.add(li_entry)
    db.session.commit()

    return "OK", 200


@LI_CONVERASTION_BLUEPRINT.route("/", methods=["GET"])
def get_li_conversation_entries_endpoint():
    """Returns a list of LinkedIn conversation entries, in the past user-defined hours"""
    hours = get_request_parameter("hours", request, required=False) or 168

    conversation_entries = get_li_conversation_entries(int(hours))

    return (
        jsonify(
            {"message": "Success", "li_conversation_entries": conversation_entries}
        ),
        200,
    )
