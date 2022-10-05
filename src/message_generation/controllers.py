from db import db

from flask import Blueprint, request
from src.research.linkedin.services import get_research_and_bullet_points_new
from src.message_generation.services import (
    approve_message,
    delete_message,
    generate_outreaches_for_batch_of_prospects,
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

    # researching prospects
    print("Research prospects ...")
    for prospect_id in tqdm(prospect_ids):
        get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

    # generating messages
    print("Generated messages ...")
    generate_outreaches_for_batch_of_prospects(prospect_list=prospect_ids)

    return "OK", 200


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
