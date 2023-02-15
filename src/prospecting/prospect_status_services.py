from model_import import (
    Prospect,
    ProspectStatus,
    ProspectEmailOutreachStatus,
    GeneratedMessageType,
    ProspectEmail,
)
from src.prospecting.models import VALID_FROM_STATUSES_MAP


def get_valid_next_prospect_statuses(prospect_id: int, channel_type):
    """
    Returns dictionary of key = status, and value = human readable.

    example:
    {
        'OPEN': 'Open',
        'IN_PROGRESS': 'In Progress',
        'CLOSED': 'Closed',
        ...
    }
    """
    channel_type = GeneratedMessageType[channel_type]
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return {}
    prospect_email: ProspectEmail = ProspectEmail.query.filter(
        ProspectEmail.id == prospect.approved_prospect_email_id
    ).first()
    current_li_status = prospect.status
    if prospect_email:
        current_email_status = prospect_email.email_status

    if channel_type == GeneratedMessageType.EMAIL:
        return ProspectEmailOutreachStatus.to_dict()
    elif channel_type == GeneratedMessageType.LINKEDIN:
        retval = ProspectStatus.to_dict()
        for status in VALID_FROM_STATUSES_MAP:
            if current_li_status not in VALID_FROM_STATUSES_MAP[status]:
                del retval[status.value]
        return retval
