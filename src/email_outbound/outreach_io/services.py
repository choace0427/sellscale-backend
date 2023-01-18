from app import db
from model_import import (
    Prospect,
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords,
    ProspectEmailStatus,
)

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


def update_status_from_csv(
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
            prospect_email_id=prospect_email.id, 
            from_status=old_outreach_status,
            to_status=new_outreach_status)
        )
        db.session.add(prospect_email)
        db.session.commit()
        update_count += 1


    if len(failed_email_list) > 0:
        return True, "Warning: Impartial write, the following emails were not found or not updatable: " + str(failed_email_list)

    return True, "Made updates to {}/{} prospects.".format(update_count, len(payload))


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
