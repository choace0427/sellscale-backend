import hashlib
import json

from app import db, celery
from model_import import ClientArchetype, GeneratedMessage, GNLPModel, Prospect
from src.email_outbound.models import (
    EmailInteractionState,
    EmailSchema,
    EmailSequenceState,
    ProspectEmail,
    ProspectEmailStatus,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSource,
    SalesEngagementInteractionSS,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords
)
from src.email_outbound.ss_data import SSData


def create_email_schema(
    name: str,
    client_archetype_id: int,
):
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        raise Exception("Client archetype not found")

    email_schema = EmailSchema(
        name=name,
        client_archetype_id=client_archetype_id,
    )
    db.session.add(email_schema)
    db.session.commit()
    return email_schema


def create_prospect_email(
    email_schema_id: int,
    prospect_id: int,
    personalized_first_line_id: int,
    batch_id: int,
):
    email_schema: EmailSchema = EmailSchema.query.get(email_schema_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    personalized_first_line: GeneratedMessage = GeneratedMessage.query.get(
        personalized_first_line_id
    )
    if not email_schema:
        raise Exception("Email schema not found")
    if not prospect:
        raise Exception("Prospect not found")
    if not personalized_first_line:
        raise Exception("Generated message not found")

    prospect_email = ProspectEmail(
        email_schema_id=email_schema_id,
        prospect_id=prospect_id,
        personalized_first_line=personalized_first_line_id,
        email_status=ProspectEmailStatus.DRAFT,
        batch_id=batch_id,
    )
    db.session.add(prospect_email)
    db.session.commit()
    return prospect_email


def batch_update_emails(
    payload: dict,
):
    for entry in payload:
        if "prospect_id" not in entry:
            return False, "Prospect ID missing in one of the rows"
        if "personalized_first_line" not in entry:
            return False, "Personalized first line missing in one of the rows"

    for entry in payload:
        prospect_id_payload: int = entry["prospect_id"]
        personalized_first_line_payload: str = entry["personalized_first_line"]

        prospect: Prospect = Prospect.query.get(prospect_id_payload)
        prospect_email_id: int = prospect.approved_prospect_email_id
        prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)

        if not prospect_email:
            continue

        personalized_first_line_id: int = prospect_email.personalized_first_line
        personalized_first_line: GeneratedMessage = GeneratedMessage.query.get(
            personalized_first_line_id
        )
        personalized_first_line.completion = personalized_first_line_payload

        db.session.add(personalized_first_line)
        db.session.commit()

    return True, "OK"


def create_sales_engagement_interaction_raw(
    client_id: int,
    client_archetype_id: int,
    client_sdr_id: int,
    payload: list,
    source: str,
) -> int:
    """Creates a SalesEngagementInteractionRaw entry using the JSON payload.
    We check the hash of the payload against payloads in the past. If the hash is the same, we return -1.
    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.
        payload (list): The JSON payload.
    Returns:
        int: The ID of the SalesEngagementInteractionRaw entry. -1 if the payload is a duplicate.
    """
    # Hash the payload so we can check against duplicates.
    json_dumps = json.dumps(payload)
    payload_hash_value: str = hashlib.sha256(json_dumps.encode()).hexdigest()
    # Check if we already have this payload in the database.
    exists = SalesEngagementInteractionRaw.query.filter_by(
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        csv_data_hash=payload_hash_value,
    ).first()
    if exists:
        return -1

    if source == SalesEngagementInteractionSource.OUTREACH.value:
        sequence_name = payload[0]["Sequence Name"]
    else:
        sequence_name = "Unknown"

    # Create a SalesEngagementInteractionRaw entry using the payload as csv_data.
    raw_entry: SalesEngagementInteractionRaw = SalesEngagementInteractionRaw(
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        csv_data=payload,
        csv_data_hash=payload_hash_value,
        source=source,
        sequence_name=sequence_name,
    )
    db.session.add(raw_entry)
    db.session.commit()
    return raw_entry.id


@celery.task(bind=True, max_retries=1)
def collect_and_update_status_from_ss_data(self, sei_ss_id: int) -> bool:
    try:
        """Collects the data from a SalesEngagementInteractionSS entry and updates the status of the prospects by broadcasting jobs to other workers.

        The nature of this task is such that it is idempotent, but potentially inefficient.
        If the task fails, it will be retried once only. If the task succeeds, it will not be retried.

        Args:
            sei_ss_id (int): _description_

        Returns:
            bool: _description_
        """
        sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(sei_ss_id)
        if not sei_ss:
            return False

        sei_ss_data = sei_ss.ss_status_data
        if not sei_ss_data or type(sei_ss_data) != list:
            return False

        for prospect_dict in sei_ss_data:
            update_status_from_ss_data.apply_async(
                (
                    sei_ss.client_id,
                    sei_ss.client_archetype_id,
                    sei_ss.client_sdr_id,
                    prospect_dict,
                )
            )

        return True
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3)
def update_status_from_ss_data(self, client_id: int, client_archetype_id: int, client_sdr_id: int, prospect_dict: dict) -> bool:
    try:
        ssdata = SSData.from_dict(prospect_dict)
        email = ssdata.get_email()
        email_interaction_state = ssdata.get_email_interaction_state()
        email_sequence_state = ssdata.get_email_sequence_state()
        if not email or not email_interaction_state or not email_sequence_state:
            return False

        # Grab prospect and prospect_email
        prospect = Prospect.query.filter_by(
            client_id=client_id,
            archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            email=email
        ).first()
        if not prospect:
            return False

        prospect_email: ProspectEmail = ProspectEmail.query.filter_by(
            prospect_id=prospect.id,
            email_status=ProspectEmailStatus.SENT,
        ).first()
        if not prospect_email:
            return False

        # Update the prospect_email
        old_outreach_status = prospect_email.outreach_status
        new_outreach_status = EMAIL_INTERACTION_STATE_TO_OUTREACH_STATUS[email_interaction_state]
        if old_outreach_status == new_outreach_status:
            return False

        if old_outreach_status == None:
            prospect_email.outreach_status = new_outreach_status
            old_outreach_status = ProspectEmailOutreachStatus.UNKNOWN
        else:
            if old_outreach_status in VALID_UPDATE_STATUSES_MAP[new_outreach_status]:
                prospect_email.outreach_status = new_outreach_status
            else:
                return False

        # Create ProspectEmailStatusRecords entry and save ProspectEmail.
        db.session.add(ProspectEmailStatusRecords(
            prospect_email_id=prospect_email.id,
            from_status=old_outreach_status,
            to_status=new_outreach_status,
        ))
        db.session.add(prospect_email)
        db.session.commit()

        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


EMAIL_INTERACTION_STATE_TO_OUTREACH_STATUS = {
    EmailInteractionState.EMAIL_SENT: ProspectEmailOutreachStatus.SENT_OUTREACH,
    EmailInteractionState.EMAIL_OPENED: ProspectEmailOutreachStatus.EMAIL_OPENED,
    EmailInteractionState.EMAIL_CLICKED: ProspectEmailOutreachStatus.ACCEPTED,
    EmailInteractionState.EMAIL_REPLIED: ProspectEmailOutreachStatus.ACTIVE_CONVO,
}

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
