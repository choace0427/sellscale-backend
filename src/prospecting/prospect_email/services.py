from datetime import datetime
from app import db, celery
from src.client.models import ClientArchetype

from src.email_outbound.models import ProspectEmail, ProspectEmailOutreachStatus
from src.prospecting.models import Prospect
from src.prospecting.services import update_prospect_status_email
from src.smartlead.smartlead import Smartlead


def check_and_remove_out_of_office_statuses() -> bool:
    """Checks all prospects for OOO statuses and removes them if necessary

    Returns:
        bool: Whether or not any OOO statuses were removed
    """
    # Get all prospects with OOO statuses
    prospect_emails: list[ProspectEmail] = ProspectEmail.query.filter(
        ProspectEmail.outreach_status == ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO
    ).all()

    for prospect_email in prospect_emails:
        # Check if the OOO status should be removed
        if (
            prospect_email.hidden_until
            and prospect_email.hidden_until < datetime.utcnow()
        ):
            # Remove the OOO status
            remove_email_out_of_office_status.delay(
                prospect_id=prospect_email.prospect_id
            )

    return True


@celery.task
def remove_email_out_of_office_status(prospect_id: int) -> tuple[bool, str]:
    """Removes the OOO status on a Prospect

    Args:
        prospect_id (int): ID of the Prospect

    Returns:
        tuple[bool, str]: Whether or not the status was removed, and the new status
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    if not prospect_email:
        return False, "No approved email found"

    # Verify that the hidden_until can be removed
    if (
        not prospect_email.hidden_until
        or prospect_email.hidden_until > datetime.utcnow()
    ):
        return False, "No hidden_until found or hidden_until is in the future"

    # Remove the hidden_until
    prospect_email.hidden_until = None
    db.session.commit()

    # Get the Smartlead Lead ID
    sl = Smartlead()
    lead = sl.get_lead_by_email_address(prospect.email)
    if not lead:
        return False, "Could not update Smartlead"
    lead_id = lead["id"]

    # Get the Smartlead campaign ID
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    smartlead_campaign_id = archetype.smartlead_campaign_id
    if not smartlead_campaign_id:
        return False, "No Smartlead campaign found"

    # Resume the Smartlead campaign
    result = sl.resume_lead_by_campaign_id(
        lead_id=lead_id, campaign_id=smartlead_campaign_id
    )
    if not result.get("ok"):
        # Edge case, mark this Prospect as NOT INTERESTED
        error = result.get("error")
        success, message = update_prospect_status_email(
            prospect_id=prospect_id,
            new_status=ProspectEmailOutreachStatus.NOT_INTERESTED,
        )
        return False, error

    # Update the status to SENT_OUTREACH
    success, message = update_prospect_status_email(
        prospect_id=prospect_id,
        new_status=ProspectEmailOutreachStatus.SENT_OUTREACH,
    )
    if not success:
        return False, message

    return True, "OOO status removed"
