from flask import Blueprint, request

from src.authentication.decorators import require_user
from src.message_generation.email.services import ai_followup_email_prompt, ai_initial_email_prompt, ai_subject_line_prompt, generate_email, generate_subject_line
from src.prospecting.models import Prospect
from src.utils.request_helpers import get_request_parameter


MESSAGE_GENERATION_EMAIL_BLUEPRINT = Blueprint(
    "message_generation/email", __name__)


@MESSAGE_GENERATION_EMAIL_BLUEPRINT.route("/initial_email", methods=["POST"])
@require_user
def post_generate_initial_email(client_sdr_id: int):
    """Generates the initial email for a Prospect."""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    template_id = get_request_parameter(
        "template_id", request, json=True, required=False, parameter_type=int
    )
    test_template = get_request_parameter(
        "test_template", request, json=True, required=False, parameter_type=str
    )
    subject_line_template_id = get_request_parameter(
        "subject_line_template_id", request, json=True, required=False, parameter_type=int
    )
    subject_line_template = get_request_parameter(
        "subject_line_template", request, json=True, required=False, parameter_type=str
    )

    # Validate
    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    if not prospect:
        return {"status": "error", "message": "Prospect not found."}, 404
    elif prospect.client_sdr_id != client_sdr_id:
        return {"status": "error", "message": "Unauthorized."}, 401

    # Get the initial email body prompt and generate the email body
    prompt = ai_initial_email_prompt(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        test_template=test_template,
        template_id=template_id
    )
    email_body = generate_email(prompt)
    email_body = email_body.get('body')

    # Get the initial email subject prompt and generate the subject line
    prompt = ai_subject_line_prompt(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        email_body=email_body,
        subject_line_template_id=subject_line_template_id,
        test_template=subject_line_template
    )
    subject_line = generate_subject_line(prompt)
    subject_line = subject_line.get('subject_line')

    return {
        'status': 'success',
        'data': {
            'email_body': {'prompt': prompt, 'completion': email_body},
            'subject_line': {'prompt': prompt, 'completion': subject_line}
        }
    }


@MESSAGE_GENERATION_EMAIL_BLUEPRINT.route("/followup_email", methods=["POST"])
@require_user
def post_generate_followup_email(client_sdr_id: int):
    """Generates the followup email for a Prospect."""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    thread_id = get_request_parameter(
        "thread_id", request, json=True, required=False, parameter_type=str
    )
    override_sequence_id = get_request_parameter(
        "override_sequence_id", request, json=True, required=False, parameter_type=int
    )
    override_template = get_request_parameter(
        "override_template", request, json=True, required=False, parameter_type=str
    )

    # Validate
    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    if not prospect:
        return {"status": "error", "message": "Prospect not found."}, 404
    elif prospect.client_sdr_id != client_sdr_id:
        return {"status": "error", "message": "Unauthorized."}, 401

    # Get the followup email body prompt and generate the email body
    prompt = ai_followup_email_prompt(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        thread_id=thread_id,
        override_sequence_id=override_sequence_id,
        override_template=override_template
    )
    email_body = generate_email(prompt)
    email_body = email_body.get('body')

    return {
        'status': 'success',
        'data': {
            'email_body': {'prompt': prompt, 'completion': email_body}
        }
    }
