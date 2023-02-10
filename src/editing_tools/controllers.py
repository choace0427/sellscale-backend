from app import db

from flask import Blueprint, request, jsonify
from src.editing_tools.services import get_edited_options, get_editing_details
from src.utils.request_helpers import get_request_parameter
from tqdm import tqdm

EDITING_TOOLS_BLUEPRINT = Blueprint("editing_tools", __name__)


@EDITING_TOOLS_BLUEPRINT.route("/edit_message", methods=["POST"])
def post_edit_message():
    message_copy = get_request_parameter(
        "message_copy", request, json=True, required=True
    )
    instruction = get_request_parameter(
        "instruction", request, json=True, required=True
    )

    edited_options = get_edited_options(
        instruction=instruction, message_copy=message_copy
    )
    return jsonify({"options": edited_options})


@EDITING_TOOLS_BLUEPRINT.route("/editing_details/<message_id>", methods=["GET"])
def get_editing_details_endpoint(message_id: int):
    return jsonify(get_editing_details(message_id))
