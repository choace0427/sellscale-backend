from numpy import require
from app import db, app

from flask import Blueprint, request, jsonify
from model_import import EmailSequenceStep
from src.client.models import ClientSDR
from src.email_sequencing.models import (
    EmailSequenceStepToAssetMapping,
    EmailSubjectLineTemplate,
    EmailTemplatePool,
    EmailTemplateType,
)
from src.email_sequencing.services import (
    activate_sequence_step,
    copy_email_template_body_item,
    copy_email_template_subject_line_item,
    create_email_sequence_step,
    create_email_sequence_step_asset_mapping,
    create_email_template_pool_item,
    deactivate_sequence_step,
    delete_email_sequence_step_asset_mapping,
    get_all_email_sequence_step_assets,
    get_email_template_pool_items,
    get_sequence_step_count_for_sdr,
    get_email_sequence_step_for_sdr,
    grade_email,
    modify_email_sequence_step,
    get_email_subject_line_template,
    create_email_subject_line_template,
    generate_email_subject_lines,
    modify_email_subject_line_template,
    modify_email_template_pool_item,
    deactivate_email_subject_line_template,
    activate_email_subject_line_template,
    undefault_all_sequence_steps_in_status,
)

from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user, rate_limit
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

    step_data: list[dict] = get_email_sequence_step_for_sdr(
        client_sdr_id=client_sdr_id,
        overall_statuses=overall_statuses_enumed,
        substatuses=substatuses,
        client_archetype_ids=client_archetype_ids,
    )

    counts = get_sequence_step_count_for_sdr(
        client_sdr_id=client_sdr_id,
        client_archetype_ids=client_archetype_ids,
    )

    return jsonify({"sequence_steps": step_data, "counts": counts}), 200


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
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
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

    # If the transformer blocklist is empty, we should extend the SDR's default blocklist
    if not transformer_blocklist or len(transformer_blocklist) == 0:
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        transformer_blocklist = sdr.default_transformer_blocklist or []

    sequence_step_id, message = create_email_sequence_step(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        title=title,
        template=template,
        overall_status=overall_status,
        bumped_count=bumped_count,
        substatus=substatus,
        # default=default,
        transformer_blocklist=transformer_blocklist,
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
    return jsonify({"error": message}), 400


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
            "sequence_delay_days",
            request,
            json=True,
            required=False,
            parameter_type=int,
        )
        or None
    )
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )

    # If transformer blocklist is not None, convert to enum
    # if transformer_blocklist:
    #     transformer_blocklist_enum = []
    #     for blocklist_item in transformer_blocklist:
    #         for key, val in ResearchPointType.__members__.items():
    #             if key == blocklist_item:
    #                 transformer_blocklist_enum.append(val)
    #                 break
    #     transformer_blocklist = transformer_blocklist_enum

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
        transformer_blocklist=transformer_blocklist,
    )

    return jsonify({"message": "Sequence step updated."}), 200 if modified else 400


@EMAIL_SEQUENCING_BLUEPRINT.route("/step/deactivate/all", methods=["POST"])
@require_user
def post_deactivate_all_sequence_steps(client_sdr_id: int):
    """Deactivates all sequence steps for a given client SDR"""
    sequence_step_id = get_request_parameter(
        "sequence_step_id", request, json=True, required=True
    )

    undefault_all_sequence_steps_in_status(
        client_sdr_id=client_sdr_id,
        sequence_step_id=sequence_step_id,
    )
    return jsonify({"status": "success", "message": "Sequence steps deactivated."}), 200


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
    active_only = get_request_parameter(
        "active_only", request, json=False, required=False, parameter_type=bool
    )

    email_subject_line_templates: list[dict] = get_email_subject_line_template(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        active_only=active_only,
    )

    return (
        jsonify(
            {
                "status": "Success",
                "data": {"subject_line_templates": email_subject_line_templates},
            }
        ),
        200,
    )


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
    is_magic_subject_line = get_request_parameter(
        "is_magic_subject_line", request, json=True, required=False, parameter_type=bool
    )

    subject_line_template_id = create_email_subject_line_template(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        subject_line=subject_line,
        is_magic_subject_line=is_magic_subject_line,
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
    return (
        jsonify(
            {
                "status": "error",
                "message": "Could not create email subject line template.",
            }
        ),
        400,
    )


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

    subject_line_template: EmailSubjectLineTemplate = (
        EmailSubjectLineTemplate.query.get(email_subject_line_template_id)
    )
    if not subject_line_template:
        return (
            jsonify(
                {"status": "error", "message": "Email subject line template not found."}
            ),
            404,
        )
    elif subject_line_template.client_sdr_id != client_sdr_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "This email subject line template does not belong to you.",
                }
            ),
            401,
        )

    modified = modify_email_subject_line_template(
        client_sdr_id=client_sdr_id,
        client_archetype_id=subject_line_template.client_archetype_id,
        email_subject_line_template_id=email_subject_line_template_id,
        subject_line=subject_line,
        active=active,
    )
    if modified:
        return (
            jsonify(
                {"status": "success", "message": "Email subject line template updated."}
            ),
            200,
        )

    return (
        jsonify(
            {
                "status": "error",
                "message": "Could not update email subject line template.",
            }
        ),
        400,
    )

@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line/generate", methods=["POST"])
@require_user
def post_generate_email_subject_lines(client_sdr_id: int):
    """Generates email subject lines based on the given archetype"""
    data = request.get_json()
    archetype_id = data.get("archetype_id")
    try:
        result = generate_email_subject_lines(client_sdr_id, archetype_id)
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Error generating subject lines: {str(e)}"}),
            500,
        )

    return jsonify({"status": "success", "data": result}), 200


@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line/delete", methods=["DELETE"])
@require_user
def delete_email_subject_line_template(client_sdr_id: int):
    """Deletes an email subject line template"""
    email_subject_line_template_id = get_request_parameter(
        "email_subject_line_template_id", request, json=True, required=True
    )

    subject_line_template: EmailSubjectLineTemplate = (
        EmailSubjectLineTemplate.query.get(email_subject_line_template_id)
    )
    if not subject_line_template:
        return (
            jsonify(
                {"status": "error", "message": "Email subject line template not found."}
            ),
            404,
        )
    elif subject_line_template.client_sdr_id != client_sdr_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "This email subject line template does not belong to you.",
                }
            ),
            401,
        )

    db.session.delete(subject_line_template)
    db.session.commit()

    return (
        jsonify(
            {"status": "success", "message": "Email subject line template deleted."}
        ),
        200,
    )



@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line/deactivate", methods=["POST"])
@require_user
def post_deactivate_email_subject_line_template(client_sdr_id: int):
    """Deactivates an email subject line template"""
    email_subject_line_template_id = get_request_parameter(
        "email_subject_line_template_id", request, json=True, required=True
    )

    subject_line_template: EmailSubjectLineTemplate = (
        EmailSubjectLineTemplate.query.get(email_subject_line_template_id)
    )
    if not subject_line_template:
        return (
            jsonify(
                {"status": "error", "message": "Email subject line template not found."}
            ),
            404,
        )
    elif subject_line_template.client_sdr_id != client_sdr_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "This email subject line template does not belong to you.",
                }
            ),
            401,
        )

    deactivated = deactivate_email_subject_line_template(
        client_sdr_id, email_subject_line_template_id
    )
    if deactivated:
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Email subject line template deactivated.",
                }
            ),
            200,
        )

    return (
        jsonify(
            {
                "status": "error",
                "message": "Could not deactivate email subject line template.",
            }
        ),
        400,
    )


@EMAIL_SEQUENCING_BLUEPRINT.route("/subject_line/activate", methods=["POST"])
@require_user
def post_activate_email_subject_line_template(client_sdr_id: int):
    """Activates an email subject line template"""
    email_subject_line_template_id = get_request_parameter(
        "email_subject_line_template_id", request, json=True, required=True
    )

    subject_line_template: EmailSubjectLineTemplate = (
        EmailSubjectLineTemplate.query.get(email_subject_line_template_id)
    )
    if not subject_line_template:
        return (
            jsonify(
                {"status": "error", "message": "Email subject line template not found."}
            ),
            404,
        )
    elif subject_line_template.client_sdr_id != client_sdr_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "This email subject line template does not belong to you.",
                }
            ),
            401,
        )

    activated = activate_email_subject_line_template(
        client_sdr_id, email_subject_line_template_id
    )
    if activated:
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Email subject line template activated.",
                }
            ),
            200,
        )

    return (
        jsonify(
            {
                "status": "error",
                "message": "Could not activate email subject line template.",
            }
        ),
        400,
    )


@EMAIL_SEQUENCING_BLUEPRINT.route("/pool", methods=["GET"])
@require_user
def get_email_pool(client_sdr_id: int):
    """Gets all templates in the email pool"""
    template_type = get_request_parameter(
        "template_type", request, json=False, required=False, parameter_type=str
    )

    # Convert template_type to enum
    template_type_enum = None
    for key, val in EmailTemplateType.__members__.items():
        if key == template_type:
            template_type_enum = val
            break
    template_type = template_type_enum

    templates: list[EmailTemplatePool] = get_email_template_pool_items(
        template_type=template_type,
        active_only=True,
    )

    return (
        jsonify(
            {
                "status": "success",
                "data": {"templates": [template.to_dict() for template in templates]},
            }
        ),
        200,
    )


@EMAIL_SEQUENCING_BLUEPRINT.route("/pool", methods=["POST"])
@require_user
def post_email_pool(client_sdr_id: int):
    """Adds a template to the email pool"""
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    template = get_request_parameter(
        "template", request, json=True, required=True, parameter_type=str
    )
    template_type = get_request_parameter(
        "template_type", request, json=True, required=True, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, parameter_type=str
    )
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )
    labels = get_request_parameter(
        "labels", request, json=True, required=False, parameter_type=list
    )
    tone = get_request_parameter(
        "tone", request, json=True, required=False, parameter_type=str
    )

    # Convert transformer blocklist to enum
    # if transformer_blocklist:
    #     transformer_blocklist_enum = []
    #     for blocklist_item in transformer_blocklist:
    #         for key, val in ResearchPointType.__members__.items():
    #             if key == blocklist_item:
    #                 transformer_blocklist_enum.append(val)
    #                 break
    #     transformer_blocklist = transformer_blocklist_enum

    # Convert template_type to enum
    template_type_enum = None
    for key, val in EmailTemplateType.__members__.items():
        if key == template_type:
            template_type_enum = val
            break
    template_type = template_type_enum

    success, id = create_email_template_pool_item(
        name=name,
        template=template,
        template_type=template_type,
        description=description,
        transformer_blocklist=transformer_blocklist,
        labels=labels,
        tone=tone,
        active=True,
    )
    if success:
        return jsonify({"status": "success", "data": {"id": id}}), 200

    return (
        jsonify(
            {"status": "error", "message": "Could not create email template pool item."}
        ),
        400,
    )


@EMAIL_SEQUENCING_BLUEPRINT.route("/pool", methods=["PATCH"])
@require_user
def patch_email_pool(client_sdr_id: int):
    """Modifies a template in the email pool"""
    pool_template_id = get_request_parameter(
        "pool_template_id", request, json=True, required=True, parameter_type=int
    )
    name = get_request_parameter(
        "name", request, json=True, required=False, parameter_type=str
    )
    template = get_request_parameter(
        "template", request, json=True, required=False, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, parameter_type=str
    )
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )
    labels = get_request_parameter(
        "labels", request, json=True, required=False, parameter_type=list
    )
    tone = get_request_parameter(
        "tone", request, json=True, required=False, parameter_type=str
    )
    active = get_request_parameter(
        "active", request, json=True, required=False, parameter_type=bool
    )

    # Convert transformer blocklist to enum
    # if transformer_blocklist:
    #     transformer_blocklist_enum = []
    #     for blocklist_item in transformer_blocklist:
    #         for key, val in ResearchPointType.__members__.items():
    #             if key == blocklist_item:
    #                 transformer_blocklist_enum.append(val)
    #                 break
    #     transformer_blocklist = transformer_blocklist_enum

    success = modify_email_template_pool_item(
        email_template_pool_item_id=pool_template_id,
        name=name,
        template=template,
        description=description,
        transformer_blocklist=transformer_blocklist,
        labels=labels,
        tone=tone,
        active=active,
    )
    if success:
        return (
            jsonify(
                {"status": "success", "message": "Email template pool item updated."}
            ),
            200,
        )

    return (
        jsonify(
            {"status": "error", "message": "Could not update email template pool item."}
        ),
        400,
    )


@EMAIL_SEQUENCING_BLUEPRINT.route("/pool/copy", methods=["POST"])
@require_user
def post_copy_email_pool_entry(client_sdr_id: int):
    """Copies a template in the email pool to the SDR's sequence"""
    template_type = get_request_parameter(
        "template_type", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    template_pool_id = get_request_parameter(
        "template_pool_id", request, json=True, required=True, parameter_type=int
    )

    if template_type == "SUBJECT_LINE":
        success = copy_email_template_subject_line_item(
            client_sdr_id=client_sdr_id,
            client_archetype_id=archetype_id,
            template_pool_id=template_pool_id,
        )
        if success:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Email subject line template copied.",
                    }
                ),
                200,
            )
    elif template_type == "BODY":
        overall_status = get_request_parameter(
            "overall_status", request, json=True, required=True, parameter_type=str
        )
        substatus = get_request_parameter(
            "substatus", request, json=True, required=False, parameter_type=str
        )
        bumped_count = get_request_parameter(
            "bumped_count", request, json=True, required=False, parameter_type=int
        )
        transformer_blocklist = get_request_parameter(
            "transformer_blocklist",
            request,
            json=True,
            required=False,
            parameter_type=list,
        )

        # Convert overall status to enum
        overall_status_enum = None
        for key, val in ProspectOverallStatus.__members__.items():
            if key == overall_status:
                overall_status_enum = val
                break
        overall_status = overall_status_enum

        # Convert transformer blocklist to enum
        # if transformer_blocklist:
        #     transformer_blocklist_enum = []
        #     for blocklist_item in transformer_blocklist:
        #         for key, val in ResearchPointType.__members__.items():
        #             if key == blocklist_item:
        #                 transformer_blocklist_enum.append(val)
        #                 break
        #     transformer_blocklist = transformer_blocklist_enum

        success = copy_email_template_body_item(
            client_sdr_id=client_sdr_id,
            client_archetype_id=archetype_id,
            template_pool_id=template_pool_id,
            overall_status=overall_status,
            substatus=substatus,
            bumped_count=bumped_count,
            transformer_blocklist=transformer_blocklist,
        )
        if success:
            return (
                jsonify(
                    {"status": "success", "message": "Email body template copied."}
                ),
                200,
            )
    else:
        return jsonify({"status": "error", "message": "Invalid template type."}), 400

    return (
        jsonify(
            {
                "status": "error",
                "message": "Could not copy email template library item.",
            }
        ),
        400,
    )


@EMAIL_SEQUENCING_BLUEPRINT.route("/grade_email", methods=["POST"])
@rate_limit(max_calls=5, time_interval=60)
def post_grade_email():
    """Grades an email, giving it a score and improvement advice"""

    subject = get_request_parameter(
        "subject", request, json=True, required=True, parameter_type=str
    )
    body = get_request_parameter(
        "body", request, json=True, required=True, parameter_type=str
    )
    tracking_data = get_request_parameter(
        "tracking_data", request, json=True, required=False, parameter_type=dict
    )

    entry_id, results = grade_email(
        tracking_data=tracking_data, subject=subject, body=body
    )

    return (
        jsonify(
            {
                "status": "success",
                "data": results,
            }
        ),
        200,
    )


@EMAIL_SEQUENCING_BLUEPRINT.route("/create_asset_mapping", methods=["POST"])
@require_user
def create_asset_mapping(client_sdr_id: int):
    """Creates an asset mapping for a given client SDR"""
    sequence_step_id = get_request_parameter(
        "sequence_step_id", request, json=True, required=True
    )
    asset_id = get_request_parameter("asset_id", request, json=True, required=True)

    sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(sequence_step_id)
    if not sequence_step:
        return jsonify({"error": "Sequence step not found."}), 404
    elif sequence_step.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This sequence step does not belong to you."}), 401

    create_email_sequence_step_asset_mapping(
        email_sequence_step_id=sequence_step_id, client_assets_id=asset_id
    )

    return jsonify({"message": "Asset mapping created."}), 200


@EMAIL_SEQUENCING_BLUEPRINT.route("/delete_asset_mapping", methods=["POST"])
@require_user
def delete_asset_mapping(client_sdr_id: int):
    """Deletes an asset mapping for a given client SDR"""
    email_sequence_step_to_asset_mapping_id = get_request_parameter(
        "email_sequence_step_to_asset_mapping_id", request, json=True, required=True
    )

    email_sequence_step_to_asset_mapping: EmailSequenceStepToAssetMapping = (
        EmailSequenceStepToAssetMapping.query.get(
            email_sequence_step_to_asset_mapping_id
        )
    )
    email_sequence_step_id: int = (
        email_sequence_step_to_asset_mapping.email_sequence_step_id
    )
    sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(
        email_sequence_step_id
    )
    if not sequence_step:
        return jsonify({"error": "Sequence step not found."}), 404
    elif sequence_step.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This sequence step does not belong to you."}), 401

    delete_email_sequence_step_asset_mapping(
        email_sequence_step_to_asset_mapping_id=email_sequence_step_to_asset_mapping_id
    )

    return jsonify({"message": "Asset mapping deleted."}), 200


@EMAIL_SEQUENCING_BLUEPRINT.route("/get_all_asset_mapping", methods=["GET"])
@require_user
def get_all_asset_mapping(client_sdr_id: int):
    """Gets all asset mapping for a given client SDR"""
    sequence_step_id = get_request_parameter(
        "sequence_step_id", request, json=False, required=True
    )

    sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(sequence_step_id)
    if not sequence_step:
        return jsonify({"error": "Sequence step not found."}), 404
    elif sequence_step.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This sequence step does not belong to you."}), 401

    mappings = get_all_email_sequence_step_assets(
        email_sequence_step_id=sequence_step_id
    )

    return jsonify({"mappings": mappings}), 200
