from app import db, celery

from src.email_classifier.out_of_office import detect_out_of_office
from src.email_outbound.models import ProspectEmailOutreachStatus
from email_validator import validate_email, EmailNotValidError
import requests
import os

from src.ml.services import chat_ai_classify_email_active_convo
from src.prospecting.services import update_prospect_status_email


@celery.task()
def classify_email(prospect_id: int, email_body: str) -> ProspectEmailOutreachStatus:
    """Classifies an email into an ACTIVE_CONVO substatuses using heuristics, classifiers, and GPT.

    Args:
        prospect_id (int): ID of the prospect
        email_body (str): Body of the email

    Returns:
        ProspectEmailOutreachStatus or None: The classified email status or None if the email is not classified
    """
    # Detect OOO - Automatically updates the prospect
    out_of_office = detect_out_of_office(prospect_id=prospect_id, email_body=email_body)
    if out_of_office:
        return ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO

    # GPT Classifier - Last step
    status = chat_ai_classify_email_active_convo(message=email_body)
    if status == ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING:
        # Perform extra logic here
        pass
    update_prospect_status_email(
        prospect_id=prospect_id,
        new_status=status,
    )

    return status


def verify_email(email: str) -> (bool, str, str):
    """Verifies if an email address is valid.

    Args:
        email (str): Email address to verify

    Returns:
        bool: True if the email is valid, False otherwise
        email: The normalized email address
        quality_score: The quality score of the email address
    """
    try:
        # Check that the email address is valid. Turn on check_deliverability
        # for first-time validations like on account creation pages (but not
        # login pages).
        emailinfo = validate_email(email, check_deliverability=True)

        # After this point, use only the normalized form of the email address,
        # especially before going to a database query.
        email = emailinfo.normalized

        # If it passes that check, let's just make sure it passes this one too.
        # This is a more strict check than the previous one.

        api_key = os.environ.get("EMAIL_VALIDATION_API_KEY")
        response = requests.get(
            f"https://emailvalidation.abstractapi.com/v1/?api_key={api_key}&email={email}"
        )
        if response.status_code != 200:
            return False, None, None

        content = response.json()

        if content.get("deliverability") != "DELIVERABLE":
            return False, None, None

        return True, email, content.get("quality_score")

    except EmailNotValidError as e:
        # The exception message is human-readable explanation of why it's
        # not a valid (or deliverable) email address.
        print(str(e))

        return False, None, None
