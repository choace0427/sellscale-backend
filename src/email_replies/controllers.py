from app import db, app

from flask import Blueprint, request, jsonify
from src.email_replies.services import (
    create_email_reply_framework,
    edit_email_reply_framework,
    get_email_reply_frameworks,
)
from src.prospecting.models import ProspectOverallStatus
from src.research.models import ResearchPointType
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user


EMAIL_REPLIES_BLUEPRINT = Blueprint("email/replies", __name__)


@EMAIL_REPLIES_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_email_replies(client_sdr_id: int):
    """Gets all EmailReplyFrameworks"""
    active_only = get_request_parameter(
        "active_only", request, json=False, required=False, parameter_type=bool
    )

    frameworks = get_email_reply_frameworks(
        client_sdr_id=client_sdr_id, active_only=active_only
    )

    return jsonify({"status": "success", "data": frameworks}), 200


@EMAIL_REPLIES_BLUEPRINT.route("/", methods=["POST"])
@require_user
def post_create_email_reply_framework(client_sdr_id: int):
    """Creates an EmailReplyFramework"""
    title = get_request_parameter(
        "title", request, json=True, required=True, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, parameter_type=str
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id",
        request,
        json=True,
        required=False,
        parameter_type=int,
    )
    substatus = get_request_parameter(
        "substatus", request, json=True, required=False, parameter_type=str
    )
    reply_instructions = get_request_parameter(
        "reply_instructions", request, json=True, required=False, parameter_type=str
    )
    use_account_research = get_request_parameter(
        "use_account_research",
        request,
        json=True,
        required=False,
        parameter_type=bool,
    )
    sellscale_generated = get_request_parameter(
        "sellscale_generated",
        request,
        json=True,
        required=False,
        parameter_type=bool,
    )
    if sellscale_generated:
        client_sdr_id = None
        client_archetype_id = None

    # Get overall_status and convert to ProspectOverallStatus
    overall_status = get_request_parameter(
        "overall_status",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )
    if overall_status:
        found_key = False
        for key, val in ProspectOverallStatus.__members__.items():
            if key == overall_status:
                overall_status = val
                found_key = True
                break
        if not found_key:
            return jsonify({"error": "Invalid overall status."}), 400

    # Get research_blocklist and convert to ResearchPointType
    research_blocklist = get_request_parameter(
        "research_blocklist",
        request,
        json=True,
        required=False,
        parameter_type=list,
    )
    enumed_research_blocklist = []
    if research_blocklist:
        for research_blocklist_item in research_blocklist:
            # Get the enum value for the research blocklist item
            found_key = False
            for key, val in ResearchPointType.__members__.items():
                if key == research_blocklist_item:
                    enumed_research_blocklist.append(val)
                    found_key = True
                    break
            if not found_key:
                return jsonify({"error": "Invalid research blocklist item."}), 400

    framework_id = create_email_reply_framework(
        title=title,
        description=description,
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        overall_status=overall_status,
        substatus=substatus,
        reply_instructions=reply_instructions,
        research_blocklist=enumed_research_blocklist,
        use_account_research=use_account_research,
    )

    return jsonify({"status": "success", "data": {"id": framework_id}}), 200


@EMAIL_REPLIES_BLUEPRINT.route("/<int:reply_framework_id>", methods=["PATCH"])
@require_user
def patch_email_reply_framework(client_sdr_id: int, reply_framework_id: int):
    """Updates an EmailReplyFramework"""
    title = get_request_parameter(
        "title", request, json=True, required=False, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, parameter_type=str
    )
    active = get_request_parameter(
        "active", request, json=True, required=False, parameter_type=bool
    )
    reply_instructions = get_request_parameter(
        "reply_instructions", request, json=True, required=False, parameter_type=str
    )
    use_account_research = get_request_parameter(
        "use_account_research",
        request,
        json=True,
        required=False,
        parameter_type=bool,
    )

    # Get research_blocklist and convert to ResearchPointType
    research_blocklist = get_request_parameter(
        "research_blocklist",
        request,
        json=True,
        required=False,
        parameter_type=list,
    )
    enumed_research_blocklist = []
    if research_blocklist:
        for research_blocklist_item in research_blocklist:
            # Get the enum value for the research blocklist item
            found_key = False
            for key, val in ResearchPointType.__members__.items():
                if key == research_blocklist_item:
                    enumed_research_blocklist.append(val)
                    found_key = True
                    break
            if not found_key:
                return jsonify({"error": "Invalid research blocklist item."}), 400

    success = edit_email_reply_framework(
        reply_framework_id=reply_framework_id,
        title=title,
        description=description,
        active=active,
        reply_instructions=reply_instructions,
        research_blocklist=enumed_research_blocklist,
        use_account_research=use_account_research,
    )
    if not success:
        return jsonify({"error": "Failed to edit Reply framework."}), 400

    return jsonify({"status": "success"}), 200
