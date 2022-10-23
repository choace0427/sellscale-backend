from app import db

from flask import Blueprint, request, jsonify
from src.research.linkedin.services import get_research_and_bullet_points_new
from src.message_generation.services import (
    approve_message,
    delete_message,
    research_and_generate_outreaches_for_prospect,
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
    cta_prompt = get_request_parameter("cta_prompt", request, json=True, required=False)

    research_and_generate_outreaches_for_prospect(
        prospect_ids=prospect_ids, cta_prompt=cta_prompt
    )

    return "OK", 200


@MESSAGE_GENERATION_BLUEPRINT.route("/batch/few_shot", methods=["POST"])
def batch_few_shot():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )
    example_ids = get_request_parameter(
        "example_ids", request, json=True, required=True
    )
    cta_prompt = get_request_parameter("cta_prompt", request, json=True, required=False)

    # todo(Aakash): implement this


@MESSAGE_GENERATION_BLUEPRINT.route("/", methods=["PATCH"])
def update():
    message_id = get_request_parameter("message_id", request, json=True, required=True)
    update = get_request_parameter("update", request, json=True, required=True)

    success = update_message(message_id=message_id, update=update)
    if success:
        return "OK", 200

    return "Failed to update", 400


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
