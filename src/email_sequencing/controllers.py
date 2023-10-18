from app import db, app

from flask import Blueprint, request, jsonify
from model_import import EmailSequenceStep
from src.email_sequencing.models import EmailSubjectLineTemplate
from src.email_sequencing.services import (
    activate_sequence_step,
    create_email_sequence_step,
    deactivate_sequence_step,
    get_sequence_step_count_for_sdr,
    get_email_sequence_step_for_sdr,
    modify_email_sequence_step,
    get_email_subject_line_template,
    create_email_subject_line_template,
    modify_email_subject_line_template,
    deactivate_email_subject_line_template,
    activate_email_subject_line_template
)
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user
from src.ml.services import (
    determine_account_research_from_convo_and_bump_framework,
    determine_best_bump_framework_from_convo,
)

from model_import import ProspectOverallStatus


EMAIL_SEQUENCING_BLUEPRINT = Blueprint("email_sequence", __name__)


@EMAIL_SEQUENCING_BLUEPRINT.route("/step", methods=["GET"])
@require_user
def get_email_sequence_steps(client_sdr_id: int):
    """Gets all bump frameworks for a given client SDR and overall status"""
    overall_statuses = (
        get_request_parameter(
            "overall_statuses", request, json=False, required=True, parameter_type=list
        )
        or []
    )
    client_archetype_ids = (
        get_request_parameter(
            "archetype_ids", request, json=False, required=False, parameter_type=list
        )
        or []
    )
    substatuses = (
        get_request_parameter(
            "substatuses", request, json=False, required=False, parameter_type=list
        )
        or []
    )

    overall_statuses_enumed = []
    for key, val in ProspectOverallStatus.__members__.items():
        if key in overall_statuses:
            overall_statuses_enumed.append(val)

    # Convert client_archetype_ids to list of integers
    if type(client_archetype_ids) == str:
        client_archetype_ids = [client_archetype_ids]
    client_archetype_ids = [int(ca_id) for ca_id in client_archetype_ids]

    bump_frameworks: list[dict] = get_email_sequence_step_for_sdr(
        client_sdr_id=client_sdr_id,
        overall_statuses=overall_statuses_enumed,
        substatuses=substatuses,
        client_archetype_ids=client_archetype_ids,
    )

    counts = get_sequence_step_count_for_sdr(
        client_sdr_id=client_sdr_id,
        client_archetype_ids=client_archetype_ids,
    )

    return jsonify({"sequence_steps": bump_frameworks, "counts": counts}), 200


@EMAIL_SEQUENCING_BLUEPRINT.route("/step", methods=["POST"])
@require_user
def post_create_sequence_step(client_sdr_id: int):
    """Create a new sequence step"""
    title = get_request_parameter(
        "title", request, json=True, required=True, parameter_type=str
    )
    template = get_request_parameter(
        "template", request, json=True, required=True, parameter_type=str
    )
    overall_status = get_request_parameter(
        "overall_status", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    default = (
        get_request_parameter(
            "default", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    bumped_count = (
        get_request_parameter(
            "bumped_count", request, json=True, required=False, parameter_type=int
        )
        or None
    )
    substatus = (
        get_request_parameter(
            "substatus", request, json=True, required=False, parameter_type=str
        )
        or None
    )

    # Get the enum value for the overall status
    found_key = False
    for key, val in ProspectOverallStatus.__members__.items():
        if key == overall_status:
            overall_status = val
            found_key = True
            break
    if not found_key:
        return jsonify({"error": "Invalid overall status."}), 400

    sequence_step_id = create_email_sequence_step(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        title=title,
        template=template,
        overall_status=overall_status,
        bumped_count=bumped_count,
        substatus=substatus,
        default=default,
    )
    if sequence_step_id:
        return (
            jsonify(
                {
                    "message": "Successfully created email sequence step",
                    "sequence_step_id": sequence_step_id,
                }
            ),
            200,
        )
    return jsonify({"error": "Could not create email sequence step."}), 400


@EMAIL_SEQUENCING_BLUEPRINT.route("/step", methods=["PATCH"])
@require_user
def patch_sequence_step(client_sdr_id: int):
    """Modifies a sequence step"""
    sequence_step_id = get_request_parameter(
        "sequence_step_id", request, json=True, required=True
    )
    title = (
        get_request_parameter(
            "title", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    template = (
        get_request_parameter(
            "template", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    default = (
        get_request_parameter(
            "default", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    bumped_count = (
        get_request_parameter(
            "bumped_count", request, json=True, required=False, parameter_type=int
        )
        or None
    )
    sequence_delay_days = (
        get_request_parameter(
            "sequence_delay_days", request, json=True, required=False, parameter_type=int
        )
        or None
    )

    sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(sequence_step_id)
    if not sequence_step:
        return jsonify({"error": "Sequence step not found."}), 404
    elif sequence_step.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This sequence step does not belong to you."}), 401

    modified = modify_email_sequence_step(
        client_sdr_id=client_sdr_id,
        client_archetype_id=sequence_step.client_archetype_id,
        sequence_step_id=sequence_step_id,
        title=title,
        template=template,
        sequence_delay_days=sequence_delay_days,
        bumped_count=bumped_count,
        default=default,
    )

    return jsonify({"message": "Sequence step updated."}), 200 if modified else 400


@EMAIL_SEQUENCING_BLUEPRINT.route("/step/deactivate", methods=["POST"])
@require_user
def post_deactivate_sequence_step(client_sdr_id: int):
    """Deletes a sequence step"""
    sequence_step_id = get_request_parameter(
        "sequence_step_id", request, json=True, required=True
    )

    sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(sequence_step_id)
    if not sequence_step:
        return jsonify({"error": "Sequence step not found."}), 404
    elif sequence_step.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This sequence step does not belong to you."}), 401

    deactivate_sequence_step(client_sdr_id, sequence_step_id)
    return jsonify({"message": "Sequence step deactivated."}), 200


@EMAIL_SEQUENCING_BLUEPRINT.route("/step/activate", methods=["POST"])
@require_user
def post_activate_sequence_step(client_sdr_id: int):
    """Activates a sequence step"""
    sequence_step_id = get_request_parameter(
        "sequence_step_id", request, json=True, required=True
    )

    sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(sequence_step_id)
    if not sequence_step:
        return jsonify({"error": "Sequence step not found."}), 404
    elif sequence_step.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This sequence step does not belong to you."}), 401

    activate_sequence_step(client_sdr_id, sequence_step_id)
    return jsonify({"message": "Sequence step activated."}), 200


@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line", methods=["GET"])
@require_user
def get_email_subject_line_templates(client_sdr_id: int):
    """Gets all email subject line templates for a given client SDR"""
    client_archetype_id = (
        get_request_parameter(
            "archetype_id", request, json=False, required=True, parameter_type=int
        )
        or None
    )
    active_only = (
        get_request_parameter(
            "active_only", request, json=False, required=False, parameter_type=bool
        )
    )

    email_subject_line_templates: list[dict] = get_email_subject_line_template(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        active_only=active_only,
    )

    return jsonify({"status": "Success", "data": {"subject_line_templates": email_subject_line_templates}}), 200


@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line", methods=["POST"])
@require_user
def post_create_email_subject_line_template(client_sdr_id: int):
    """Create a new email subject line template"""
    subject_line = get_request_parameter(
        "subject_line", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    subject_line_template_id = create_email_subject_line_template(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        subject_line=subject_line,
    )
    if subject_line_template_id:
        return (
            jsonify(
                {
                    "status": "success",
                    "data": {"subject_line_template_id": subject_line_template_id},
                }
            ),
            200,
        )
    return jsonify({"status": "error", "message": "Could not create email subject line template."}), 400


@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line", methods=["PATCH"])
@require_user
def patch_email_subject_line_template(client_sdr_id: int):
    """Modifies an email subject line template"""
    email_subject_line_template_id = get_request_parameter(
        "email_subject_line_template_id", request, json=True, required=True
    )
    subject_line = get_request_parameter(
        "subject_line", request, json=True, required=False, parameter_type=str
    )
    active = get_request_parameter(
        "active", request, json=True, required=False, parameter_type=bool
    )

    subject_line_template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.get(email_subject_line_template_id)
    if not subject_line_template:
        return jsonify({"status": "error", "message": "Email subject line template not found."}), 404
    elif subject_line_template.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "This email subject line template does not belong to you."}), 401

    modified = modify_email_subject_line_template(
        client_sdr_id=client_sdr_id,
        client_archetype_id=subject_line_template.client_archetype_id,
        email_subject_line_template_id=email_subject_line_template_id,
        subject_line=subject_line,
        active=active,
    )
    if modified:
        return jsonify({"status": "success", "message": "Email subject line template updated."}), 200

    return jsonify({"status": "error", "message": "Could not update email subject line template."}), 400


@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line/deactivate", methods=["POST"])
@require_user
def post_deactivate_email_subject_line_template(client_sdr_id: int):
    """Deactivates an email subject line template"""
    email_subject_line_template_id = get_request_parameter(
        "email_subject_line_template_id", request, json=True, required=True
    )

    subject_line_template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.get(email_subject_line_template_id)
    if not subject_line_template:
        return jsonify({"status": "error", "message": "Email subject line template not found."}), 404
    elif subject_line_template.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "This email subject line template does not belong to you."}), 401

    deactivated = deactivate_email_subject_line_template(client_sdr_id, email_subject_line_template_id)
    if deactivated:
        return jsonify({"status": "success", "message": "Email subject line template deactivated."}), 200

    return jsonify({"status": "error", "message": "Could not deactivate email subject line template."}), 400


@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line/activate", methods=["POST"])
@require_user
def post_activate_email_subject_line_template(client_sdr_id: int):
    """Activates an email subject line template"""
    email_subject_line_template_id = get_request_parameter(
        "email_subject_line_template_id", request, json=True, required=True
    )

    subject_line_template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.get(email_subject_line_template_id)
    if not subject_line_template:
        return jsonify({"status": "error", "message": "Email subject line template not found."}), 404
    elif subject_line_template.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "This email subject line template does not belong to you."}), 401

    activated = activate_email_subject_line_template(client_sdr_id, email_subject_line_template_id)
    if activated:
        return jsonify({"status": "success", "message": "Email subject line template activated."}), 200

    return jsonify({"status": "error", "message": "Could not activate email subject line template."}), 400


# @BUMP_FRAMEWORK_BLUEPRINT.route("/autofill_research", methods=["POST"])
# @require_user
# def post_autofill_research_bump_framework(client_sdr_id: int):
#     """Autofill account research based on a sequence step and convo history"""

#     prospect_id = get_request_parameter(
#         "prospect_id", request, json=True, required=True
#     )
#     convo_history = get_request_parameter(
#         "convo_history", request, json=True, required=True
#     )
#     bump_framework_desc = get_request_parameter(
#         "bump_framework_desc", request, json=True, required=True
#     )
#     account_research = get_request_parameter(
#         "account_research", request, json=True, required=True
#     )

#     research_indexes = determine_account_research_from_convo_and_bump_framework(
#         prospect_id, convo_history, bump_framework_desc, account_research
#     )

#     return (
#         jsonify(
#             {
#                 "message": "Determined best account research points",
#                 "data": research_indexes,
#             }
#         ),
#         200,
#     )


# @BUMP_FRAMEWORK_BLUEPRINT.route("/autoselect_framework", methods=["POST"])
# @require_user
# def post_autoselect_bump_framework(client_sdr_id: int):
#     """Autoselect sequence step based on convo history"""

#     convo_history = get_request_parameter(
#         "convo_history", request, json=True, required=True
#     )
#     bump_framework_ids = get_request_parameter(
#         "bump_framework_ids", request, json=True, required=True
#     )

#     framework_index = determine_best_bump_framework_from_convo(
#         convo_history, bump_framework_ids
#     )

#     return (
#         jsonify(
#             {
#                 "message": "Determined index of best sequence step",
#                 "data": framework_index,
#             }
#         ),
#         200,
#     )
