from model_import import (
    Prospect,
    ProspectStatus,
    ProspectEmailOutreachStatus,
    GeneratedMessageType,
    ProspectEmail,
)


def get_valid_next_prospect_statuses(prospect_id: int, channel_type) -> dict:
    """ Returns dictionary with valid next statuses for the prospect and all statuses available in the channel

    Args:
        prospect_id (int): ID of the prospect
        channel_type (str): Channel type to get statuses for

    Returns:
        dict: Dictionary with valid next statuses for the prospect and all statuses available in the channel
    """
    # Get channel type, if exists.
    if channel_type not in ("LINKEDIN", "EMAIL"):
        return {}
    channel_type = GeneratedMessageType[channel_type]

    # Get Prospect and Prospect Email record
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return {}
    prospect_email: ProspectEmail = ProspectEmail.query.filter(
        ProspectEmail.id == prospect.approved_prospect_email_id
    ).first()

    # Get current statuses
    current_li_status = prospect.status
    if prospect_email:
        current_email_status = prospect_email.outreach_status or ProspectEmailOutreachStatus.UNKNOWN

    # Construct empty state statuses
    valid_next_statuses = {}
    all_statuses = {}

    # Construct valid next statuses for Email
    if channel_type == GeneratedMessageType.EMAIL:
        if not prospect_email:
            return {"message": "Prospect does not have an approved email"}
        valid_next_statuses = ProspectEmailOutreachStatus.valid_next_statuses(current_email_status)
        all_statuses = ProspectEmailOutreachStatus.status_descriptions()

    # Construct valid next statuses for LinkedIn
    if channel_type == GeneratedMessageType.LINKEDIN:
        valid_next_statuses = ProspectStatus.valid_next_statuses(current_li_status)
        all_statuses = ProspectStatus.status_descriptions()

    return {
        "valid_next_statuses": valid_next_statuses,
        "all_statuses": all_statuses
    }
