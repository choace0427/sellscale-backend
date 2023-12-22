from app import db, celery

from src.email_classifier.out_of_office import detect_out_of_office
from src.email_outbound.models import ProspectEmailOutreachStatus


@celery.task()
def classify_email(
    prospect_id: int, email_body: str
) -> ProspectEmailOutreachStatus or None:
    """Classifies an email into an ACTIVE_CONVO substatuses using heuristics, classifiers, and GPT.

    Args:
        prospect_id (int): ID of the prospect
        email_body (str): Body of the email

    Returns:
        ProspectEmailOutreachStatus or None: The classified email status or None if the email is not classified
    """
    out_of_office = detect_out_of_office(prospect_id=prospect_id, email_body=email_body)
    if out_of_office:
        return ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO

    return None
