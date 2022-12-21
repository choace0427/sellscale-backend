from flask import Blueprint, request
from src.ml_adversary.models import AdversaryTrainingPoint
from src.ml_adversary.services import (
    preview_fix,
    create_adversary_training_point, 
    toggle_adversary_training_point,
    edit_adversary_training_point)
from src.utils.request_helpers import get_request_parameter

ML_ADVERSARY_BLUEPRINT = Blueprint("adversary", __name__)


@ML_ADVERSARY_BLUEPRINT.route("/train", methods=["POST"])
def train_adversary():
    pass


@ML_ADVERSARY_BLUEPRINT.route("/preview_fix", methods=["POST"])
def preview_fix_controller():
    """ Previews the fix for a given completion.
    
    Returns:
        preview, status: Preview and status code for the request.
    """
    completion = get_request_parameter("completion", request, json=True, required=True)
    fix = get_request_parameter("fix", request, json=True, required=True)

    preview, status = preview_fix(completion, fix)
    return {
        "preview": preview,
    }, status


@ML_ADVERSARY_BLUEPRINT.route("/create", methods=["POST"])
def create_adversary():
    """ Creates a new training point for the adversary model.

    Returns:
        message, status: Message and status code for the request.
    """
    generated_message_id = get_request_parameter("generated_message_id", request, json=True, required=True)
    mistake_description = get_request_parameter("mistake_description", request, json=True, required=True)
    fix_instructions = get_request_parameter("fix_instructions", request, json=True, required=True)

    message, status = create_adversary_training_point(generated_message_id, mistake_description, fix_instructions)
    return message, status


@ML_ADVERSARY_BLUEPRINT.route("/toggle_point", methods=["POST"])
def toggle_training_point():
    """ Toggles whether a training point is used in training.

    Returns:
        message, status: Message and status code for the request.
    """
    training_point_id = get_request_parameter("training_point_id", request, json=True, required=True)
    toggle_on = get_request_parameter("toggle_on", request, json=True, required=True)

    message, status = toggle_adversary_training_point(training_point_id, toggle_on)
    return message, status


@ML_ADVERSARY_BLUEPRINT.route("/edit", methods=["POST"])
def edit_training_point():
    """ Edits a training point for the adversary model.
    
    Returns:
        message, status: Message and status code for the request.
    """
    training_point_id = get_request_parameter("training_point_id", request, json=True, required=True)
    mistake_description = get_request_parameter("mistake_description", request, json=True, required=True)
    fix_instructions = get_request_parameter("fix_instructions", request, json=True, required=True)
    
    message, status = edit_adversary_training_point(training_point_id, mistake_description, fix_instructions)
    return message, status
