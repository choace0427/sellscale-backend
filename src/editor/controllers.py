from app import db

from flask import Blueprint, request, jsonify
from src.utils.request_helpers import get_request_parameter
from src.editor.services import create_editor, update_editor, toggle_editor_active


EDITOR_BLUEPRINT = Blueprint("editor", __name__)


@EDITOR_BLUEPRINT.route("/create", methods=["POST"])
def post_create_editor():
    name = get_request_parameter("name", request, json=True, required=True)
    email = get_request_parameter("email", request, json=True, required=True)
    editor_type = get_request_parameter(
        "editor_type", request, json=True, required=True
    )

    editor = create_editor(name=name, email=email, editor_type=editor_type)
    if editor:
        return "OK", 200
    return "Could not create editor.", 400


@EDITOR_BLUEPRINT.route("/update", methods=["POST"])
def post_update_editor():
    name = get_request_parameter("name", request, json=True, required=True)
    email = get_request_parameter("email", request, json=True, required=True)
    editor_type = get_request_parameter(
        "editor_type", request, json=True, required=True
    )

    editor = update_editor(name=name, email=email, editor_type=editor_type)
    if editor:
        return "OK", 200
    return "Could not update editor.", 400


@EDITOR_BLUEPRINT.route("/toggle_active", methods=["POST"])
def post_toggle_editor_active():
    editor_id = get_request_parameter("editor_id", request, json=True, required=True)

    editor = toggle_editor_active(editor_id=editor_id)
    if editor:
        return "OK", 200
    return "Could not update editor.", 400
