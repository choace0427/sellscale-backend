from flask import Blueprint, request
from src.email_sequencing.models import EmailSubjectLineTemplate

from src.authentication.decorators import require_user
from src.message_generation.email.services import (
    ai_followup_email_prompt,
    ai_initial_email_prompt,
    ai_multichannel_email_prompt,
    ai_subject_line_prompt,
    generate_email,
    generate_subject_line,
)
from src.ml.openai_wrappers import OPENAI_CHAT_GPT_4_MODEL
from src.ml.spam_detection import run_algorithmic_spam_detection
from src.prospecting.models import Prospect
from src.utils.request_helpers import get_request_parameter


MESSAGE_GENERATION_EMAIL_BLUEPRINT = Blueprint("message_generation/email", __name__)


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
        "subject_line_template_id",
        request,
        json=True,
        required=False,
        parameter_type=int,
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
    body_prompt = ai_initial_email_prompt(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        test_template=test_template,
        template_id=template_id,
    )
    email_body = generate_email(prompt=body_prompt, model=OPENAI_CHAT_GPT_4_MODEL)
    email_body = email_body.get("body")

    # Get the initial email subject prompt and generate the subject line
    # Get the EmailSubjectLineTemplate if it exists
    subject_line = subject_line_template
    if subject_line_template_id:
        subject_line_template: EmailSubjectLineTemplate = (
            EmailSubjectLineTemplate.query.filter_by(
                id=subject_line_template_id
            ).first()
        )
        subject_line = subject_line_template.subject_line

    subject_line_strict = False
    if subject_line_template:
        subject_line_strict = "[[" not in subject_line and "{{" not in subject_line

    if subject_line_strict:
        subject_prompt = (
            "No AI template detected in subject line template. Using exact template."
        )
        subject_line = subject_line
    else:
        subject_prompt = ai_subject_line_prompt(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            email_body=email_body,
            subject_line_template_id=subject_line_template_id,
            test_template=subject_line_template,
        )
        subject_line = generate_subject_line(subject_prompt)
        subject_line = subject_line.get("subject_line")

    body_spam_results = run_algorithmic_spam_detection(text=email_body)
    subject_spam_results = run_algorithmic_spam_detection(text=subject_line)

    return {
        "status": "success",
        "data": {
            "email_body": {
                "prompt": body_prompt,
                "completion": email_body,
                "spam_detection_results": body_spam_results,
            },
            "subject_line": {
                "prompt": subject_prompt,
                "completion": subject_line,
                "spam_detection_results": subject_spam_results,
            },
        },
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

    prompt = ai_followup_email_prompt(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        thread_id=thread_id,
        override_sequence_id=override_sequence_id,
        override_template=override_template,
    )
    if not prompt:
        return None
    email_body = generate_email(
        prompt=prompt,
        model=OPENAI_CHAT_GPT_4_MODEL,
    )
    email_body = email_body.get("body")

    body_spam_results = run_algorithmic_spam_detection(text=email_body)

    return {
        "status": "success",
        "data": {
            "email_body": {
                "prompt": prompt,
                "completion": email_body,
                "spam_detection_results": body_spam_results,
            }
        },
    }


@MESSAGE_GENERATION_EMAIL_BLUEPRINT.route("/multichannel_email", methods=["POST"])
@require_user
def post_generate_multichannel_email(client_sdr_id: int):
    """Generates the multichannel email for a Prospect."""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    # Validate
    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    if not prospect:
        return {"status": "error", "message": "Prospect not found."}, 404
    elif prospect.client_sdr_id != client_sdr_id:
        return {"status": "error", "message": "Unauthorized."}, 401

    prompt = ai_multichannel_email_prompt(
        prospect_id=prospect_id,
    )
    if not prompt:
        return None
    email_body = generate_email(
        prompt=prompt,
        model=OPENAI_CHAT_GPT_4_MODEL,
    )
    email_body = email_body.get("body")
    email_body.replace("\n", "")

    body_spam_results = run_algorithmic_spam_detection(text=email_body)

    return {
        "status": "success",
        "data": {
            "email_body": {
                "prompt": prompt,
                "completion": email_body,
                "spam_detection_results": body_spam_results,
            }
        },
    }
