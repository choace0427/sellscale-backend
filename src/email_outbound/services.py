import hashlib
import json
import datetime

from app import db, celery
from model_import import (
    ClientArchetype,
    GeneratedMessage,
    Prospect,
    ProspectStatus,
    GeneratedMessageStatus,
    GeneratedMessageType,
)
from src.campaigns.models import (
    OutboundCampaign,
    OutboundCampaignStatus,
)
from src.email_outbound.models import (
    EmailInteractionState,
    EmailSchema,
    ProspectEmail,
    ProspectEmailStatus,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSource,
    SalesEngagementInteractionSS,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords,
    VALID_UPDATE_EMAIL_STATUS_MAP,
)
from src.email_outbound.ss_data import SSData


def create_prospect_email(
    prospect_id: int,
    personalized_first_line_id: int,
    batch_id: int,
):
    prospect: Prospect = Prospect.query.get(prospect_id)
    personalized_first_line: GeneratedMessage = GeneratedMessage.query.get(
        personalized_first_line_id
    )
    if not prospect:
        raise Exception("Prospect not found")
    if not personalized_first_line:
        raise Exception("Generated message not found")

    prospect_email = ProspectEmail(
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


def batch_mark_prospect_email_sent(prospect_ids: list[int], campaign_id: int) -> bool:
    """Uses the prospect_ids list to broadcast tasks to celery to upload the elevant prospect email statuses

    Args:
        prospect_ids (list[int]): List of prospect IDs
        campaign_id (int): ID of the campaign

    Returns:
        bool: True if successful

    """
    for prospect_id in prospect_ids:
        update_prospect_email_flow_statuses.apply_async(args=[prospect_id, campaign_id])

    return True


@celery.task(bind=True, max_retries=1)
def update_prospect_email_flow_statuses(
    self, prospect_id: int, campaign_id: int
) -> tuple[str, bool]:
    """Updates all the statuses as part of the prospect_email flow

    prospect_email -> email_status, date_sent
    prospect -> status
    generated_message -> message_status
    outbound_campaign -> status

    Args:
        prospect_id (int): ID of the prospect

    Returns:
        tuple[str, bool]: (error message, success)
    """
    try:
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            return "Prospect {} not found".format(prospect_id), False

        if prospect.approved_prospect_email_id:
            # Updates to prospect_email
            prospect_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )
            prospect_email.email_status = ProspectEmailStatus.SENT
            prospect_email.date_sent = datetime.datetime.now()

            # Updates to generated_message
            personalized_first_line: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_first_line
            )
            personalized_first_line.message_status = GeneratedMessageStatus.SENT

            # Updates to outbound_campaign
            campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
            if campaign and campaign.campaign_type == GeneratedMessageType.LINKEDIN:
                return "Campaign {} is not an email campaign".format(campaign.id), False
            campaign.status = OutboundCampaignStatus.COMPLETE

            # Commit
            db.session.add(campaign)
            db.session.add(prospect_email)
            db.session.add(prospect)
            db.session.add(personalized_first_line)
            db.session.commit()
        else:
            return (
                "Prospect {} does not have an approved prospect email".format(
                    prospect.id
                ),
                False,
            )

        return "", True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=Exception("Retrying task"))


def create_sales_engagement_interaction_raw(
    client_id: int,
    client_sdr_id: int,
    payload: list,
    source: str,
    sequence_name="Unknown",
) -> int:
    """Creates a SalesEngagementInteractionRaw entry using the JSON payload.
    We check the hash of the payload against payloads in the past. If the hash is the same, we return -1.
    Args:
        client_id (int): The client ID.
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
        client_sdr_id=client_sdr_id,
        csv_data_hash=payload_hash_value,
    ).first()
    if exists:
        return -1

    if source == SalesEngagementInteractionSource.OUTREACH.value:
        sequence_name = payload[0]["Sequence Name"]
    else:
        sequence_name = sequence_name

    # Create a SalesEngagementInteractionRaw entry using the payload as csv_data.
    raw_entry: SalesEngagementInteractionRaw = SalesEngagementInteractionRaw(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        csv_data=payload,
        csv_data_hash=payload_hash_value,
        source=source,
        sequence_name=sequence_name,
    )
    db.session.add(raw_entry)
    db.session.commit()
    return raw_entry.id


def get_approved_prospect_email_by_id(prospect_id: int):
    """Returns the approved prospect email for a prospect

    Args:
        prospect_id (int): ID of the prospect

    Returns:
        ProspectEmail: The approved prospect email
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None

    if not prospect.approved_prospect_email_id:
        return None

    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    return prospect_email


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
        sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(
            sei_ss_id
        )
        if not sei_ss:
            return False

        sei_ss_data = sei_ss.ss_status_data
        if not sei_ss_data or type(sei_ss_data) != list:
            return False

        for prospect_dict in sei_ss_data:
            update_status_from_ss_data.apply_async(
                (sei_ss.client_id, sei_ss.client_sdr_id, prospect_dict, sei_ss.id)
            )

        return True
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3)
def update_status_from_ss_data(
    self, client_id: int, client_sdr_id: int, prospect_dict: dict, sei_ss_id: int
) -> tuple[str, bool]:
    """Updates the status of a prospect based on the data from a SalesEngagementInteractionSS entry.

    Args:
        client_id (int): ID of the client.
        client_sdr_id (int): ID of the client SDR.
        prospect_dict (dict): the dictionary representing the SS Data
        sei_ss_id (int): ID of the SalesEngagementInteractionSS entry.

    Raises:
        self.retry: If the task fails, it will be retried up to 3 times.

    Returns:
        tuple[str, bool]: A tuple containing the error message and a boolean indicating whether the task succeeded.
    """
    try:
        ssdata = SSData.from_dict(prospect_dict)
        email = ssdata.get_email()
        email_interaction_state = ssdata.get_email_interaction_state()
        email_sequence_state = ssdata.get_email_sequence_state()
        if not email or not email_interaction_state or not email_sequence_state:
            return False

        # Grab prospect and prospect_email
        prospect: Prospect = Prospect.query.filter_by(
            client_id=client_id, client_sdr_id=client_sdr_id, email=email
        ).first()
        if not prospect:
            return (
                "Prospect with email {} could not be found for sdr {}".format(
                    email, client_sdr_id
                ),
                False,
            )

        prospect_email: ProspectEmail = ProspectEmail.query.filter_by(
            prospect_id=prospect.id,
            email_status=ProspectEmailStatus.SENT,
        ).first()
        if not prospect_email:
            return (
                "Prospect {} does not have an approved prospect email".format(
                    prospect.id
                ),
                False,
            )

        # Update the prospect_email
        old_outreach_status = prospect_email.outreach_status
        new_outreach_status = EMAIL_INTERACTION_STATE_TO_OUTREACH_STATUS[
            email_interaction_state
        ]
        if old_outreach_status == new_outreach_status:
            return (
                "No update needed: {} to {}".format(
                    old_outreach_status, new_outreach_status
                ),
                True,
            )

        if old_outreach_status == None:
            prospect_email.outreach_status = new_outreach_status
            old_outreach_status = ProspectEmailOutreachStatus.UNKNOWN
        else:
            if (
                old_outreach_status
                in VALID_UPDATE_EMAIL_STATUS_MAP[new_outreach_status]
            ):
                prospect_email.outreach_status = new_outreach_status
            else:
                return (
                    "Invalid update from {} to {}".format(
                        old_outreach_status, new_outreach_status
                    ),
                    False,
                )

        # Create ProspectEmailStatusRecords entry and save ProspectEmail.
        db.session.add(
            ProspectEmailStatusRecords(
                prospect_email_id=prospect_email.id,
                from_status=old_outreach_status,
                to_status=new_outreach_status,
                sales_engagement_interaction_ss_id=sei_ss_id,
            )
        )
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
