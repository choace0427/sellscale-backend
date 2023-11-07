from flask import Blueprint, request, jsonify
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from model_import import LinkedinInitialMessageTemplateLibrary
from src.li_conversation.services_linkedin_initial_message_templates import (
    create_new_linkedin_initial_message_template,
    toggle_linkedin_initial_message_template_active_status,
    update_linkedin_initial_message_template,
    get_all_linkedin_initial_message_templates,
)

LINKEDIN_TEMPLATE_BLUEPRINT = Blueprint("linkedin_template", __name__)

@LINKEDIN_TEMPLATE_BLUEPRINT.route("/linkedin_initial_message_templates", methods=["GET"])
def get_linkedin_initial_message_templates():
    """Gets all active LinkedIn initial message templates"""
    templates = get_all_linkedin_initial_message_templates()
    return jsonify({"linkedin_initial_message_templates": templates}), 200

@LINKEDIN_TEMPLATE_BLUEPRINT.route("/linkedin_initial_message_templates", methods=["POST"])
def post_create_linkedin_initial_message_template():
    """Create a new LinkedIn initial message template"""
    name = get_request_parameter("name", request, json=True, required=True, parameter_type=str)
    raw_prompt = get_request_parameter("raw_prompt", request, json=True, required=True, parameter_type=str)
    human_readable_prompt = get_request_parameter("human_readable_prompt", request, json=True, required=True, parameter_type=str)
    length = get_request_parameter("length", request, json=True, required=True, parameter_type=str)
    transformer_blocklist = get_request_parameter("transformer_blocklist", request, json=True, required=False, parameter_type=list)
    tone = get_request_parameter("tone", request, json=True, required=False, parameter_type=str)
    labels = get_request_parameter("labels", request, json=True, required=False, parameter_type=list)

    create_new_linkedin_initial_message_template(
        name=name,
        raw_prompt=raw_prompt,
        human_readable_prompt=human_readable_prompt,
        length=length,
        transformer_blocklist=transformer_blocklist,
        tone=tone,
        labels=labels,
    )
    return jsonify({"message": "Successfully created LinkedIn initial message template"}), 200

@LINKEDIN_TEMPLATE_BLUEPRINT.route("/linkedin_initial_message_templates/<int:template_id>", methods=["PATCH"])
def patch_linkedin_initial_message_template(template_id: int):
    """Modifies a LinkedIn initial message template"""
    name = get_request_parameter("name", request, json=True, required=False, parameter_type=str)
    raw_prompt = get_request_parameter("raw_prompt", request, json=True, required=False, parameter_type=str)
    human_readable_prompt = get_request_parameter("human_readable_prompt", request, json=True, required=False, parameter_type=str)
    length = get_request_parameter("length", request, json=True, required=False, parameter_type=str)
    transformer_blocklist = get_request_parameter("transformer_blocklist", request, json=True, required=False, parameter_type=list)
    tone = get_request_parameter("tone", request, json=True, required=False, parameter_type=str)
    labels = get_request_parameter("labels", request, json=True, required=False, parameter_type=list)

    update_linkedin_initial_message_template(
        li_template_id=template_id,
        name=name,
        raw_prompt=raw_prompt,
        human_readable_prompt=human_readable_prompt,
        length=length,
        transformer_blocklist=transformer_blocklist,
        tone=tone,
        labels=labels,
    )
    return jsonify({"message": "Successfully updated LinkedIn initial message template"}), 200

@LINKEDIN_TEMPLATE_BLUEPRINT.route("/linkedin_initial_message_templates/toggle_active_status/<int:template_id>", methods=["POST"])
def post_toggle_linkedin_initial_message_template_active_status(template_id: int):
    """Toggles active status of a LinkedIn initial message template"""
    toggle_linkedin_initial_message_template_active_status(li_template_id=template_id)
    return jsonify({"message": "Successfully toggled LinkedIn initial message template active status"}), 200
