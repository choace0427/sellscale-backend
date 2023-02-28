from model_import import (
    Prospect,
    ProspectStatus,
    ProspectEmailOutreachStatus,
    GeneratedMessageType,
    ProspectEmail,
)

VALID_NEXT_LINKEDIN_STATUSES = {
    ProspectStatus.PROSPECTED: [
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.SENT_OUTREACH,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.SENT_OUTREACH: [
        ProspectStatus.ACCEPTED,
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.ACCEPTED: [
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.RESPONDED: [
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.ACTIVE_CONVO: [
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.SCHEDULING: [
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.DEMO_SET: [
        ProspectStatus.DEMO_WON,
        ProspectStatus.DEMO_LOSS,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.NOT_INTERESTED: [
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.NOT_QUALIFIED: [],
}


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
    if channel_type not in ("LINKEDIN", "EMAIL"):
        return {}
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
        retval = {}
        valid_next_statuses = [
            x.value for x in VALID_NEXT_LINKEDIN_STATUSES[current_li_status]
        ]
        for status in ProspectStatus.to_dict():
            if status in valid_next_statuses:
                retval[status] = ProspectStatus.to_dict()[status]

        return retval
