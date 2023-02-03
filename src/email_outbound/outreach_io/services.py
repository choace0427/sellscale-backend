from app import db, celery
from model_import import (
    Prospect,
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords,
    ProspectEmailStatus,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSource,
    SalesEngagementInteractionSS,
    EmailInteractionState,
    EmailSequenceState
)
from src.email_outbound.services import (create_ss_prospect_dict)

EMAIL = "Email"
SEQUENCE_STATE = "Sequence State"
EMAILED = "Emailed?"
OPENED = "Opened?"
CLICKED = "Clicked?"
REPLIED = "Replied?"
FINISHED = "Finished"


def validate_outreach_csv_payload(payload: list) -> tuple:
    """ Validates the CSV payload from Outreach.io (submitted from Retool)

    Args:
        payload (list): The payload from Outreach.io

    Returns:
        tuple: (bool, str) - (True if valid, message)
    """
    if len(payload) == 0:
        return False, "No rows in payload"

    prospect = payload[0]
    fields_in_csv= set()
    all_required_fields = {EMAIL, SEQUENCE_STATE, EMAILED, OPENED, CLICKED, REPLIED}
    for field in all_required_fields:
        if field in prospect:
            fields_in_csv.add(field)

    missing = all_required_fields - fields_in_csv
    if len(missing) > 0:
        return False, "CSV payload is missing required fields: {}".format(missing)

    return True, "OK"


def convert_outreach_payload_to_ss(
    client_id: int,
    client_archetype_id: int,
    client_sdr_id: int,
    sales_engagement_interaction_raw_id: int,
    payload: list,
) -> int:
    """Converts the Outreach.io payload into a SalesEngagementInteractionSS entry

    Args:
        client_id (int): The client ID
        client_archetype_id (int): The client archetype ID
        client_sdr_id (int): The client SDR ID
        sales_engagement_interaction_raw_id (int): The SalesEngagementInteractionRaw ID
        payload (list): The Outreach.io payload

    Returns:
        int: The SalesEngagementInteractionSS ID
    """
    list_ss_prospects = []
    for prospect_dict in payload:
        email = prospect_dict.get(EMAIL)
        outreach_sequence_state = prospect_dict.get(SEQUENCE_STATE)
        if outreach_sequence_state == "Finished":
            sequence_state = EmailSequenceState.COMPLETED
        elif outreach_sequence_state == "Bounced":
            sequence_state = EmailSequenceState.BOUNCED
        elif outreach_sequence_state == "Paused OOTO":
            sequence_state = EmailSequenceState.OUT_OF_OFFICE
        elif outreach_sequence_state == "Active":
            sequence_state = EmailSequenceState.IN_PROGRESS
        else:
            sequence_state = EmailSequenceState.UNKNOWN

        if prospect_dict.get(REPLIED):
            interaction_state = EmailInteractionState.EMAIL_REPLIED
        elif prospect_dict.get(CLICKED):
            interaction_state = EmailInteractionState.EMAIL_CLICKED
        elif prospect_dict.get(OPENED):
            interaction_state = EmailInteractionState.EMAIL_OPENED
        elif prospect_dict.get(EMAILED):
            interaction_state = EmailInteractionState.EMAIL_SENT
        else:
            interaction_state = EmailInteractionState.UNKNOWN

        ss_prospect_dict = create_ss_prospect_dict(
            email=email,
            email_interaction_state=interaction_state,
            email_sequence_state=sequence_state,
        )
        list_ss_prospects.append(ss_prospect_dict)

    sei_ss = SalesEngagementInteractionSS(
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        sales_engagement_interaction_raw_id=sales_engagement_interaction_raw_id,
        ss_status_data=list_ss_prospects,
    )
    db.session.add(sei_ss)
    db.session.commit()
    return sei_ss.id


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def update_status_from_csv(
    self,
    payload: list,
    client_id: int,
) -> tuple:
    """ Updates the status of the prospects from the CSV payload from Outreach.io (submitted from Retool)

    Args:
        payload (list): The payload from Outreach.io
        client_id (int): The client id, used to verify the prospect belongs to the client

    Returns:
        tuple: (bool, str) - (True if valid, message)

    TODO: ProspectEmail is currently not a one-to-one mapping to Prospect. It needs to be in the future.
    """
    try:
        if len(payload) == 0:
            return False, "No rows in payload"

        # This list will be used to return the emails that were not found belonging to the specified client id
        failed_email_list = []
        update_count = 0

        for prospect_dict in payload:
            email = prospect_dict.get(EMAIL)
            sequence_state = prospect_dict.get(SEQUENCE_STATE)
            if sequence_state != FINISHED:
                continue

            # Get the correct prospect. Needs to match on email AND client id
            prospect_list = Prospect.query.filter_by(email=email).all()
            prospect: Prospect = None
            for p in prospect_list:
                if p.client_id == client_id:
                    prospect = p
                    break
            if not prospect:
                failed_email_list.append(email)
                continue

            prospect_email: ProspectEmail = ProspectEmail.query.filter_by(
                prospect_id=prospect.id,
                email_status=ProspectEmailStatus.SENT,
            ).first()
            prospect_email_id = prospect_email.id
            if not prospect_email:
                failed_email_list.append(email)
                continue

            old_outreach_status = prospect_email.outreach_status
            new_outreach_status = get_new_status(prospect_dict)
            if old_outreach_status == new_outreach_status:
                continue

            if old_outreach_status == None:
                prospect_email.outreach_status = new_outreach_status
                old_outreach_status = ProspectEmailOutreachStatus.UNKNOWN
            else:
                if old_outreach_status in VALID_UPDATE_STATUSES_MAP[new_outreach_status]:
                    prospect_email.outreach_status = new_outreach_status
                else:
                    failed_email_list.append(email)
                    continue

            db.session.add(ProspectEmailStatusRecords(
                prospect_email_id=prospect_email_id,
                from_status=old_outreach_status,
                to_status=new_outreach_status)
            )
            db.session.add(prospect_email)
            db.session.commit()
            update_count += 1


        if len(failed_email_list) > 0:
            return True, "Warning: Impartial write, the following emails were not found or not updatable: " + str(failed_email_list)

        return True, "Made updates to {}/{} prospects.".format(update_count, len(payload))
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)

def get_new_status(prospect: dict) -> ProspectEmailOutreachStatus:
    """ Gets the new status from the prospect dict (from payload)

    Args:
        prospect (dict): The prospect dict

    Returns:
        ProspectEmailOutreachStatus: The new status
    """
    replied = prospect.get(REPLIED)
    clicked = prospect.get(CLICKED)
    opened = prospect.get(OPENED)
    emailed = prospect.get(EMAILED)
    if replied == "Yes":
        return ProspectEmailOutreachStatus.ACTIVE_CONVO
    elif clicked == "Yes":
        return ProspectEmailOutreachStatus.ACCEPTED
    elif opened == "Yes":
        return ProspectEmailOutreachStatus.EMAIL_OPENED
    elif emailed == "Yes":
        return ProspectEmailOutreachStatus.SENT_OUTREACH


# key (new_status) : value (list of valid statuses to update from)
VALID_UPDATE_STATUSES_MAP = {
    ProspectEmailOutreachStatus.EMAIL_OPENED: [ProspectEmailOutreachStatus.SENT_OUTREACH],
    ProspectEmailOutreachStatus.ACCEPTED: [ProspectEmailOutreachStatus.EMAIL_OPENED, ProspectEmailOutreachStatus.SENT_OUTREACH],
    ProspectEmailOutreachStatus.ACTIVE_CONVO: [
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
    ],
    ProspectEmailOutreachStatus.SCHEDULING: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
    ],
    ProspectEmailOutreachStatus.NOT_INTERESTED: [
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.SCHEDULING,
    ],
    ProspectEmailOutreachStatus.DEMO_SET: [
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.SCHEDULING,
    ],
    ProspectEmailOutreachStatus.DEMO_WON: [ProspectEmailOutreachStatus.DEMO_SET],
    ProspectEmailOutreachStatus.DEMO_LOST: [ProspectEmailOutreachStatus.DEMO_SET],
}
