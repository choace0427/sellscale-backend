from app import db

from flask import Blueprint, request, jsonify
from src.message_generation.services import (
    approve_message,
    delete_message,
    research_and_generate_outreaches_for_prospect_list,
    update_message,
)
from src.utils.request_helpers import get_request_parameter
from tqdm import tqdm

MESSAGE_GENERATION_BLUEPRINT = Blueprint("message_generation", __name__)


@MESSAGE_GENERATION_BLUEPRINT.route("/batch", methods=["POST"])
def index():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )
    cta_id = get_request_parameter("cta_id", request, json=True, required=False)

    research_and_generate_outreaches_for_prospect_list(
        prospect_ids=prospect_ids, cta_id=cta_id
    )

    return "OK", 200


@MESSAGE_GENERATION_BLUEPRINT.route("/", methods=["PATCH"])
def update():
    message_id = get_request_parameter("message_id", request, json=True, required=True)
    update = get_request_parameter("update", request, json=True, required=True)

    success = update_message(message_id=message_id, update=update)
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/batch_update", methods=["PATCH"])
def batch_update_messages():
    """
    payload = [
        {
            "linkedin_url": "linkedin.com/in/jameszw",
            "id": 2028,
            "full_name": "James Wang",
            "title": "VP of Sales Ops & Strategy at Velocity Global",
            "company": "Velocity Global",
            "completion": "This is a test 1\n",
            "message_id": 36582,
        },
        ...
    ]
    """
    payload = get_request_parameter("payload", request, json=True, required=True)
    for prospect in payload:
        message_id = prospect["message_id"]
        update = prospect["completion"]
        update_message(message_id=message_id, update=update)

    return "OK", 200


@MESSAGE_GENERATION_BLUEPRINT.route("/approve", methods=["POST"])
def approve():
    message_id = get_request_parameter("message_id", request, json=True, required=True)

    success = approve_message(message_id=message_id)
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/", methods=["DELETE"])
def delete():
    message_id = get_request_parameter("message_id", request, json=True, required=True)

    success = delete_message(message_id=message_id)
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/mass_update", methods=["POST"])
def mass_update_generated_messages():
    from model_import import Prospect, GeneratedMessage

    payload = get_request_parameter("payload", request, json=True, required=True)
    ids = []
    for item in payload:
        prospect_id = item["Prospect ID"]
        update = item["Message"]

        p: Prospect = Prospect.query.get(prospect_id)
        approved_message_id: int = p.approved_outreach_message_id
        message: GeneratedMessage = GeneratedMessage.query.get(approved_message_id)
        if not message:
            continue

        message.completion = update
        db.session.add(message)
        db.session.commit()

        ids.append(message.id)

    return jsonify({"message_ids": ids})


@MESSAGE_GENERATION_BLUEPRINT.route("/create_cta", methods=["POST"])
def post_create_cta():
    from src.message_generation.services import create_cta

    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    text_value = get_request_parameter("text_value", request, json=True, required=True)

    cta = create_cta(archetype_id=archetype_id, text_value=text_value)
    return jsonify({"cta_id": cta.id})


@MESSAGE_GENERATION_BLUEPRINT.route("/delete_cta", methods=["DELETE"])
def delete_cta_request():
    from src.message_generation.services import delete_cta

    cta_id = get_request_parameter("cta_id", request, json=True, required=True)

    success = delete_cta(cta_id=cta_id)
    if success:
        return "OK", 200

    return "Failed to delete", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/toggle_cta_active", methods=["POST"])
def post_toggle_cta_active():
    from src.message_generation.services import toggle_cta_active

    cta_id = get_request_parameter("cta_id", request, json=True, required=True)

    success = toggle_cta_active(cta_id=cta_id)
    if success:
        return "OK", 200

    return "Failed to toggle", 400
