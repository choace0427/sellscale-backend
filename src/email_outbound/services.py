import hashlib
import json
import datetime
import re
from typing import Optional
from bs4 import BeautifulSoup
from flask import jsonify
from src.bump_framework_email.models import BumpFrameworkEmail
from src.client.models import ClientSDR
from src.email_outbound.models import Sequence, SequenceStatus

from app import db, celery
from model_import import (
    ClientArchetype,
    GeneratedMessage,
    Prospect,
    ProspectChannels,
    ProspectStatus,
    GeneratedMessageStatus,
    GeneratedMessageType,
)
from src.campaigns.models import (
    OutboundCampaign,
    OutboundCampaignStatus,
)
from src.ml.openai_wrappers import OPENAI_CHAT_GPT_4_MODEL, wrapped_chat_gpt_completion
from src.prospecting.services import calculate_prospect_overall_status
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
from src.automation.slack_notification import send_status_change_slack_block


def create_prospect_email(
    prospect_id: int,
    outbound_campaign_id: int,
    personalized_first_line_id: Optional[int] = None,
    personalized_subject_line_id: Optional[int] = None,
    personalized_body_id: Optional[int] = None,
):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        raise Exception("Prospect not found")

    prospect_email = ProspectEmail(
        prospect_id=prospect_id,
        # personalized_first_line=personalized_first_line_id,
        personalized_subject_line=personalized_subject_line_id,
        personalized_body=personalized_body_id,
        email_status=ProspectEmailStatus.DRAFT,
        outbound_campaign_id=outbound_campaign_id,
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
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect_email_id)

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


def batch_mark_prospects_in_email_campaign_queued(campaign_id: int):
    outbound_campaign: OutboundCampaign = OutboundCampaign.query.get(
        campaign_id)
    if not outbound_campaign:
        return False, "Campaign not found"
    outbound_campaign.status = OutboundCampaignStatus.COMPLETE
    outbound_campaign.calculate_cost()
    db.session.add(outbound_campaign)

    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(outbound_campaign.prospect_ids)
    ).all()
    bulk_updates = []
    time_index = datetime.datetime.utcnow()
    for prospect in prospects:
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect.approved_prospect_email_id)
        prospect_email.outreach_status = ProspectEmailOutreachStatus.QUEUED_FOR_OUTREACH
        prospect_email.email_status = ProspectEmailStatus.SENT

        # set date_scheduled to a time between 9am and 5pm on a weekday. keep it at a 5 minute interval from previous email
        time_index = time_index + datetime.timedelta(minutes=5)
        if time_index.hour > 17:  # nothing after 5p PST
            try:
                time_index = datetime.datetime(
                    time_index.year,
                    time_index.month,
                    time_index.day + 1,
                    9,
                    0,
                    0,
                )
            except:
                time_index = datetime.datetime(
                    time_index.year,
                    (time_index.month + 1) % 12,
                    1,
                    9,
                    0,
                    0,
                )
        if time_index.isoweekday() > 5:  # skip weekends
            time_index = datetime.datetime(
                time_index.year,
                time_index.month,
                (time_index.day + 3) % 7 + 1,
                9,
                0,
                0,
            )
        prospect_email.date_scheduled_to_send = time_index

        bulk_updates.append(prospect_email)

    db.session.bulk_save_objects(bulk_updates)
    db.session.commit()

    return True


@celery.task
def send_prospect_emails():
    """
    Sends all the prospect emails that need to be sent at a given time
    """
    prospect_emails: list[ProspectEmail] = ProspectEmail.query.filter(
        ProspectEmail.outreach_status
        == ProspectEmailOutreachStatus.QUEUED_FOR_OUTREACH,
        ProspectEmail.date_scheduled_to_send <= datetime.datetime.utcnow(),
    ).all()
    print("Sending {} emails".format(len(prospect_emails)))
    for prospect_email in prospect_emails:
        send_prospect_email.apply_async(args=[prospect_email.id], countdown=10)


@celery.task
def send_prospect_email(prospect_email_id: int):
    """
    Sends the prospect email via Nylas and updates the prospect_email status to SENT.
    Also updates prospect email status to SENT and updates any relevant generated messages to SENT
    as well.
    """
    from src.prospecting.nylas.services import nylas_send_email

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)

    if (
        not prospect_email
        or prospect_email.outreach_status
        != ProspectEmailOutreachStatus.QUEUED_FOR_OUTREACH
    ):
        return False

    outbound_campaign: OutboundCampaign = OutboundCampaign.query.get(
        prospect_email.outbound_campaign_id
    )
    client_sdr_id = outbound_campaign.client_sdr_id
    prospect_id = prospect_email.prospect_id

    prospect_email.outreach_status = ProspectEmailOutreachStatus.SENT_OUTREACH
    prospect_email.email_status = ProspectEmailStatus.SENT
    prospect_email.date_sent = datetime.datetime.now()
    db.session.add(prospect_email)

    # Updates to generated_message
    gm_line_ids = [
        prospect_email.personalized_first_line,
        prospect_email.personalized_subject_line,
        prospect_email.personalized_body,
    ]
    generated_messages: list[GeneratedMessage] = GeneratedMessage.query.filter(
        GeneratedMessage.id.in_(gm_line_ids)
    ).all()
    for generated_message in generated_messages:
        generated_message.message_status = GeneratedMessageStatus.SENT
        db.session.add(generated_message)
    db.session.commit()

    subject_line_gm = GeneratedMessage.query.get(
        prospect_email.personalized_subject_line
    )
    body_gm = GeneratedMessage.query.get(prospect_email.personalized_body)

    subject = subject_line_gm.completion
    body = body_gm.completion
    # replace all "\n" with </br> for html formatting
    body = body.replace("\n", "</br>")

    nylas_send_email(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        subject=subject,
        body=body,
        prospect_email_id=prospect_email_id,
    )


def batch_mark_prospect_email_sent(prospect_ids: list[int], campaign_id: int) -> bool:
    """Uses the prospect_ids list to broadcast tasks to celery to upload the elevant prospect email statuses

    Args:
        prospect_ids (list[int]): List of prospect IDs
        campaign_id (int): ID of the campaign

    Returns:
        bool: True if successful

    """
    for prospect_id in prospect_ids:
        update_prospect_email_flow_statuses.apply_async(
            args=[prospect_id, campaign_id])

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
            campaign: OutboundCampaign = OutboundCampaign.query.get(
                campaign_id)
            if campaign and campaign.campaign_type == GeneratedMessageType.LINKEDIN:
                return "Campaign {} is not an email campaign".format(campaign.id), False
            campaign.status = OutboundCampaignStatus.COMPLETE

            # Calculate the cost
            campaign.calculate_cost()

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
        return exists.id

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
        prospect_id = prospect.id

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

        # Send a slack message if the new status is active convo (responded)
        if new_outreach_status == ProspectEmailOutreachStatus.ACTIVE_CONVO:
            send_status_change_slack_block(
                outreach_type=ProspectChannels.EMAIL,
                prospect=prospect,
                new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                custom_message=" responded to your email! 🙌🏽",
                metadata={},
            )
        elif (
            new_outreach_status == ProspectEmailOutreachStatus.SCHEDULING
        ):  # Scheduling
            send_status_change_slack_block(
                outreach_type=ProspectChannels.EMAIL,
                prospect=prospect,
                new_status=ProspectEmailOutreachStatus.SCHEDULING,
                custom_message=" is scheduling! 🙏🔥",
                metadata={},
            )
        elif new_outreach_status == ProspectEmailOutreachStatus.DEMO_SET:  # Demo Set
            send_status_change_slack_block(
                outreach_type=ProspectChannels.EMAIL,
                prospect=prospect,
                new_status=ProspectEmailOutreachStatus.DEMO_SET,
                custom_message=" set a time to demo!! 🎉🎉🎉",
                metadata={},
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

        calculate_prospect_overall_status(prospect_id)

        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def update_prospect_email_outreach_status(
    prospect_email_id: int, new_status: ProspectEmailOutreachStatus
):
    """Updates the outreach status of a prospect email.

    Args:
        prospect_email_id (int): ID of the prospect email.
        new_status (ProspectEmailOutreachStatus): The new outreach status.
    """
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    if not prospect_email:
        return False

    old_status = prospect_email.outreach_status
    if old_status == new_status:
        return False

    if old_status in VALID_UPDATE_EMAIL_STATUS_MAP[new_status]:
        prospect_email.outreach_status = new_status
        db.session.add(prospect_email)
        db.session.commit()

    return True


EMAIL_INTERACTION_STATE_TO_OUTREACH_STATUS = {
    EmailInteractionState.EMAIL_SENT: ProspectEmailOutreachStatus.SENT_OUTREACH,
    EmailInteractionState.EMAIL_OPENED: ProspectEmailOutreachStatus.EMAIL_OPENED,
    EmailInteractionState.EMAIL_CLICKED: ProspectEmailOutreachStatus.ACCEPTED,
    EmailInteractionState.EMAIL_REPLIED: ProspectEmailOutreachStatus.ACTIVE_CONVO,
}


def add_sequence(title: str, client_sdr_id: int, archetype_id: int, data):
    """Add a sequence to the database.

    Args:
        title (str): Title of the sequence.
        client_sdr_id (int): ID of the SDR.
        archetype_id (int): ID of the archetype.
        data (_type_): JSON data for the sequence, { subject: str, body: str }[]

    Returns:
        (JSON, HTTP status): JSON response and HTTP status code.
    """

    ca: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.id == archetype_id,
    ).first()
    if not ca:
        return jsonify({"message": "Archetype not found for this SDR"}), 404

    sequence = Sequence(
        title=title,
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        # TODO: Confirm the JSON data is valid?
        data=data,
        status=SequenceStatus.PENDING,
        sales_engagement_id=None,
    )
    db.session.add(sequence)
    db.session.commit()

    return jsonify({"message": "Created", "data": sequence.to_dict()}), 200


def get_sequences(client_sdr_id: int, archetype_id: int):
    """Get all sequences for a given archetype.

    Args:
        client_sdr_id (int): ID of the SDR.
        archetype_id (int): ID of the archetype.

    Returns:
        (JSON, HTTP status): JSON response and HTTP status code.
    """
    sequences = Sequence.query.filter(
        Sequence.archetype_id == archetype_id,
        Sequence.client_sdr_id == client_sdr_id,
    ).all()
    return (
        jsonify({"message": "Success", "data": [
                s.to_dict() for s in sequences]}),
        200,
    )


def generate_email_bump(
    client_sdr_id: int,
    prospect_id: int,
    email_thread_id: str,
    email_bump_framework_id: Optional[int] = None,
    custom_account_research: Optional[list[str]] = None,
    max_attempts: Optional[int] = 3,
) -> (str, str):
    """Generates a response to an email thread using Bump Frameworks.

    Args:


    Returns:
        (str, str): The response and the GPT-3 prompt.
    """
    # Get SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get Prospect
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None, None

    # Get Email Bump Framework, if any
    email_bump_framework: Optional[BumpFrameworkEmail] = None
    email_structure: str = "Write a medium length email that follows the thread."
    if email_bump_framework_id:
        email_bump_framework = BumpFrameworkEmail.query.get(email_bump_framework_id)
        if email_bump_framework:
            blocks = email_bump_framework.email_blocks

            # Join the blocks with a number and newline
            for i, block in enumerate(blocks):
                blocks[i] = f"{i+1}. {block}"
            email_structure = "\n".join(blocks)

    # Get Email Thread transcript
    email_thread_transcript: list[dict] = get_email_messages_with_prospect_transcript_format(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        thread_id=email_thread_id
    )
    if len(email_thread_transcript) == 0:
        return None, None

    prompt = """You are {sdr_name} who is writing an email as part of an email thread. Keep responses friendly and concise.

Use the following email structure when composing the email:
{email_structure}

Use the following custom personalization points when composing the email:
{custom_personalization_points}

Here is a transcript of the email thread so far:
=== EMAIL THREAD TRANSCRIPT ===
{email_thread_transcript}
=== END EMAIL THREAD TRANSCRIPT ===

""".format(
    sdr_name=sdr.name,
    email_structure=email_structure,
    custom_personalization_points="\n".join(custom_account_research) if custom_account_research else "",
    email_thread_transcript="\n\n".join(email_thread_transcript)
)

    for i in range(max_attempts):
        try:
            # Get response from Chat
            response = wrapped_chat_gpt_completion(
                [
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                model=OPENAI_CHAT_GPT_4_MODEL
            )
            print(response)

            return response, prompt
        except:
            pass

    return "Generation failed after 3 attempts", prompt


def get_email_messages_with_prospect_transcript_format(
    client_sdr_id: int, prospect_id: int, thread_id: str, x: Optional[int] = None
) -> list[str]:
    """Gets the messages between a ClientSDR and a Prospect in a transcript format. Optionally, can limit the number of messages returned.

    Returns in the format:
    [
        "(Name) (ClientSDR) (date_received): > Message",
        "(Name) (Prospect) (date_received): > Message",
        "(Name) (Other) (date_received): > Message",
        ...
    ]

    Oldest message first.

    Args:
        client_sdr_id (int): ID of the ClientSDR
        prospect_id (int): ID of the Prospect
        thread_id (str): ID of the EmailConversationThread
        x (Optional[int], optional): Number of messages to return. Defaults to None.

    Returns:
        list[str]: List of messages in transcript format
    """
    from src.prospecting.nylas.services import get_email_messages_with_prospect

    messages: list[dict] = get_email_messages_with_prospect(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        thread_id=thread_id,
        x=x,
    )
    if not messages or len(messages) == 0:
        return []
    messages.reverse()

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    sdr_name: str = sdr.name
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_name: str = prospect.full_name

    transcript: list[str] = []
    for message in messages:
        date_received = message.get('date_received')
        sender_name = ''
        sender_class = ''
        body = ''

        # Parse the email body
        body: str = message.get('body')
        bs = BeautifulSoup(body, 'html.parser')
        body: str = bs.get_text()
        body: str = re.sub(r"\n+", "\n", body)
        body: str = "> " + body
        body: str = body.strip().replace("\n", "\n> ")

        from_sdr = message.get('from_sdr')
        from_prospect = message.get('from_prospect')
        if from_sdr:
            sender_name = sdr_name
            sender_class = 'SDR'
        elif from_prospect:
            sender_name = prospect_name
            sender_class = 'Prospect'
        else:
            sender_name = message.get('message_from', [{'name': ''}])[0].get('name')
            sender_class = 'Other'

        transcript.append(f"({sender_name}) ({sender_class}) ({date_received}):\n{body}")

    return transcript
