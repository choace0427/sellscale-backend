import datetime
import re
from typing import List, Optional, Tuple

import markdown
from sqlalchemy.orm.attributes import flag_modified

from bs4 import BeautifulSoup
import pytz
from src.email_scheduling.models import EmailMessagingSchedule, EmailMessagingType
from src.email_sequencing.models import EmailSequenceStep
from src.message_generation.email.services import create_email_automated_reply_entry
from src.message_generation.models import GeneratedMessage
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)
from src.utils.datetime.dateparse_utils import (
    convert_string_to_datetime,
    convert_string_to_datetime_or_none,
)
from src.ml.services import get_text_generation
from src.utils.email.html_cleaning import clean_html

from src.utils.lists import chunk_list
from src.client.models import Client, SDREmailBank

from src.prospecting.services import update_prospect_status_email

from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.prospecting.models import Prospect, ProspectInSmartlead, ProspectOverallStatus

from src.utils.slack import send_slack_message, URL_MAP

from src.client.models import Client, ClientArchetype, ClientSDR
from src.smartlead.smartlead import (
    Lead,
    Smartlead,
    SmartleadCampaignStatisticEntry,
)

from app import db, celery


def get_smartlead_inbox(client_sdr_id: int) -> dict:
    """Gets the prospect IDs that have replied (via Smartlead) for a given SDR.

    Args:
        client_sdr_id (int): The ID of the SDR

    Returns:
        list[dict]: A list of emails
    """
    # Get all prospects that have replied
    inbox_query = f"""SELECT
	p.id,
    p.full_name,
    p.title,
    p.img_url,
    p.icp_fit_score,
	a.smartlead_campaign_id,
    pe.outreach_status,
    pe.last_reply_time,
    pe.last_message
FROM
	prospect p
	LEFT JOIN prospect_email pe ON p.approved_prospect_email_id = pe.id
	LEFT JOIN client_archetype a ON p.archetype_id = a.id
WHERE
	pe.outreach_status::text ilike 'ACTIVE_CONVO%'
	AND (pe.hidden_until IS NULL
		OR pe.hidden_until < now())
	AND p.client_sdr_id = {client_sdr_id}
	AND a.smartlead_campaign_id IS NOT NULL;;
"""
    ids = db.session.execute(inbox_query).fetchall()
    replied_prospects = []
    for id in ids:
        replied_prospects.append(
            {
                "prospect_id": id[0],
                "prospect_name": id[1],
                "prospect_title": id[2],
                "prospect_img_url": id[3],
                "prospect_icp_fit_score": id[4],
                "smartlead_campaign_id": id[5],
                "outreach_status": id[6],
                "last_reply_time": id[7],
                "last_message": id[8],
            }
        )

    snoozed_query = f"""SELECT
	p.id,
    p.full_name,
    p.title,
    p.img_url,
    p.icp_fit_score,
	a.smartlead_campaign_id,
    pe.hidden_until,
    pe.outreach_status,
    pe.last_reply_time,
    pe.last_message
FROM
	prospect p
	LEFT JOIN prospect_email pe ON p.approved_prospect_email_id = pe.id
	LEFT JOIN client_archetype a ON p.archetype_id = a.id
WHERE
	pe.outreach_status::text ilike 'ACTIVE_CONVO%'
	AND pe.hidden_until > now()
	AND p.client_sdr_id = {client_sdr_id}
	AND a.smartlead_campaign_id IS NOT NULL;;
"""
    ids = db.session.execute(snoozed_query).fetchall()
    snoozed_prospects = []
    for id in ids:
        snoozed_prospects.append(
            {
                "prospect_id": id[0],
                "prospect_name": id[1],
                "prospect_title": id[2],
                "prospect_img_url": id[3],
                "prospect_icp_fit_score": id[4],
                "smartlead_campaign_id": id[5],
                "hidden_until": id[6],
                "outreach_status": id[7],
                "last_reply_time": id[8],
                "last_message": id[9],
            }
        )

    demo_query = f"""SELECT
	p.id,
    p.full_name,
    p.title,
    p.img_url,
    p.icp_fit_score,
	a.smartlead_campaign_id,
    pe.outreach_status,
    pe.last_reply_time,
    pe.last_message
FROM
	prospect p
	LEFT JOIN prospect_email pe ON p.approved_prospect_email_id = pe.id
	LEFT JOIN client_archetype a ON p.archetype_id = a.id
WHERE
	pe.outreach_status = 'DEMO_SET'
	AND p.client_sdr_id = {client_sdr_id}
	AND a.smartlead_campaign_id IS NOT NULL;;
"""
    ids = db.session.execute(demo_query).fetchall()
    demo_prospects = []
    for id in ids:
        demo_prospects.append(
            {
                "prospect_id": id[0],
                "prospect_name": id[1],
                "prospect_title": id[2],
                "prospect_img_url": id[3],
                "prospect_icp_fit_score": id[4],
                "smartlead_campaign_id": id[5],
                "outreach_status": id[6],
                "last_reply_time": id[7],
                "last_message": id[8],
            }
        )

    return {
        "inbox": replied_prospects,
        "snoozed": snoozed_prospects,
        "demo": demo_prospects,
    }


def backfill_processing_webhooks():
    # Get the smartleadwebhookpayload
    from src.smartlead.webhooks.models import (
        SmartleadWebhookPayloads,
        SmartleadWebhookProcessingStatus,
    )

    payloads: list[SmartleadWebhookPayloads] = (
        SmartleadWebhookPayloads.query.filter(
            SmartleadWebhookPayloads.processing_status
            == SmartleadWebhookProcessingStatus.PROCESSING
        )
        .order_by(SmartleadWebhookPayloads.id.asc())
        .all()
    )

    for payload in payloads:
        print(f"{payload.id} - {payload.smartlead_webhook_type.value}")
        type = payload.smartlead_webhook_type.value
        if type == "email.sent":
            from src.smartlead.webhooks.email_sent import process_email_sent_webhook

            process_email_sent_webhook(payload.id)
        elif type == "email.opened":
            from src.smartlead.webhooks.email_opened import process_email_opened_webhook

            process_email_opened_webhook(payload.id)
        elif type == "email.replied":
            from src.smartlead.webhooks.email_replied import (
                process_email_replied_webhook,
            )

            process_email_replied_webhook(payload.id)
        elif type == "email.bounced":
            from src.smartlead.webhooks.email_bounced import (
                process_email_bounce_webhook,
            )

            process_email_bounce_webhook(payload.id)
        elif type == "email.link_clicked":
            from src.smartlead.webhooks.email_link_clicked import (
                process_email_link_clicked_webhook,
            )

            process_email_link_clicked_webhook(payload.id)

    return True


def get_message_history_for_prospect(
    prospect_id: int,
    smartlead_campaign_id: Optional[int] = None,
) -> list[dict]:
    """Gets the message history for a given prospect

    Args:
        prospect_id (int): The ID of the prospect
        smartlead_campaign_id (Optional[int], optional): The ID of the Smartlead campaign. Defaults to None.

    Returns:
        list[dict]: A list of messages
    """
    prospect: Prospect = Prospect.query.get(prospect_id)

    sl = Smartlead()
    smartlead_lead = sl.get_lead_by_email_address(prospect.email)
    smartlead_prospect_id = smartlead_lead.get("id")
    if not smartlead_prospect_id:
        return []

    if not smartlead_campaign_id:
        archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
        smartlead_campaign_id = archetype.smartlead_campaign_id

    message_history = sl.get_message_history_using_lead_and_campaign_id(
        lead_id=smartlead_prospect_id, campaign_id=smartlead_campaign_id
    )
    history = message_history["history"]

    return history


@celery.task
def smartlead_reply_to_prospect(
    prospect_id: int, email_body: str, cc: Optional[list]
) -> bool:
    """Replies to a prospect via Smartlead

    Args:
        prospect_id (int): The ID of the prospect
        email_body (str): The body of the email

    Returns:
        bool: True if successful
    """
    from src.slack.notifications.email_ai_reply_notification import (
        EmailAIReplyNotification,
    )

    # Get the prospect, archetype, and smartlead campaign ID
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return False
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    if not prospect_email:
        return False
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    campaign_id = archetype.smartlead_campaign_id
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    # Get the message history for the prospect
    message_history = get_message_history_for_prospect(prospect_id=prospect_id)
    if not message_history:
        return False

    sl = Smartlead()

    # Work backwards, we are replying to the last message sent
    # The last message will be the last REPLY message
    for message in reversed(message_history):
        if message["type"] == "REPLY":
            last_message = message
            stats_id = last_message["stats_id"]
            reply_message_id = last_message["message_id"]
            reply_email_time = last_message["time"]
            reply_email_body = last_message["email_body"]
            break

    if not last_message:
        return False

    # Send the reply
    response = sl.reply_to_lead(
        campaign_id=campaign_id,
        email_stats_id=stats_id,
        email_body=email_body,
        reply_message_id=reply_message_id,
        reply_email_time=reply_email_time,
        reply_email_body=reply_email_body,
        cc=cc,
    )
    if not response:
        return False

    # SLACK NOTIFICATION
    # Get the pretty email body
    reply_email_body = clean_html(html=reply_email_body, remove_past_convo=True)
    reply_email_body = reply_email_body.replace("\n", "\n>")

    # Get the pretty reply
    message = clean_html(html=email_body, remove_past_convo=False)
    message.replace("\n", "\n>")

    webhook_urls: List[str] = []
    client: Client = Client.query.get(prospect.client_id)
    webhook_urls.append(
        client.pipeline_notifications_webhook_url
        if (client and client.pipeline_notifications_webhook_url)
        else URL_MAP["eng-sandbox"]
    )

    # Send the Slack message
    success = create_and_send_slack_notification_class_message(
        notification_type=SlackNotificationType.AI_REPLY_TO_EMAIL,
        arguments={
            "client_sdr_id": client_sdr.id,
            "prospect_id": prospect_id,
            "prospect_message": reply_email_body,
            "ai_response": message,
        },
    )

    # notification = EmailAIReplyNotification(
    #     client_sdr_id=client_sdr.id,
    #     developer_mode=False,
    #     prospect_id=prospect_id,
    #     prospect_message=reply_email_body,
    #     ai_response=message,
    # )
    # success = notification.send_notification(preview_mode=False)

    # Mark the prospect email as hidden until 3 days from now
    p_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    p_email.hidden_until = datetime.datetime.utcnow() + datetime.timedelta(days=3)
    db.session.commit()

    return True


def get_email_warmings(client_sdr_id: Optional[int] = None) -> list[dict]:
    """Gets all email warmings, or all email warmings for a given SDR

    Args:
        client_sdr_id (Optional[int], optional): The ID of the SDR. Defaults to None.

    Returns:
        list[dict]: A list of email warmings
    """
    sl = Smartlead()

    # If a client SDR ID is provided, get the warmings for the registered email banks
    if client_sdr_id:
        # Get all the email banks that belong to this SDR that have a Smartlead account ID
        email_banks: list[SDREmailBank] = SDREmailBank.query.filter(
            SDREmailBank.client_sdr_id == client_sdr_id,
            SDREmailBank.smartlead_account_id.isnot(None),
        ).all()

        warmings = []
        for email_bank in email_banks:
            warming = sl.get_emails(username=email_bank.email_address)
            if warming:
                warmings.extend(warming)
    else:
        warmings = sl.get_emails()

    return warmings


def get_archetype_emails(archetype_id: int) -> list[dict]:
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)

    if not archetype or not archetype.smartlead_campaign_id:
        return []

    sl = Smartlead()
    warmings = sl.get_campaign_email_accounts(
        campaign_id=archetype.smartlead_campaign_id
    )

    email_banks: list[SDREmailBank] = SDREmailBank.query.filter_by(
        client_sdr_id=archetype.client_sdr_id,
    ).all()

    email_banks = [
        email_bank
        for email_bank in email_banks
        if email_bank.smartlead_account_id is not None
    ]

    # Added warming data to the email bank
    banks = [email_bank.to_dict() for email_bank in email_banks]
    for email_bank in banks:
        for warming in warmings:
            if email_bank.get("smartlead_account_id") == warming["id"]:
                email_bank["warming"] = warming
                break

    # # Added email bank active status to the warming
    # for warming in warmings:
    #     for email_bank in email_banks:
    #         if email_bank.smartlead_account_id == warming["id"]:
    #             warming["active"] = email_bank.active
    #             break

    return banks


def get_warmup_percentage(sent_count: int) -> int:
    TOTAL_SENT = 100

    return min(round((sent_count / TOTAL_SENT) * 100, 0), 100)


def sync_smartlead_send_schedule(archetype_id: int) -> tuple[bool, str]:
    """Syncs the Smartlead send schedule for a given archetype

    Args:
        archetype_id (int): The ID of the archetype

    Returns:
        tuple[bool, str]: A tuple with the first value being True if successful, and the second being a message
    """
    # 1. Get the archetype
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or not archetype.smartlead_campaign_id:
        return False, "Archetype not found"

    # 2. Get the SDR
    client_sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
    if not client_sdr:
        return False, "SDR not found"

    # 3. Get the email sequence
    delay_days = 0
    sequence = []
    sequence_intro: EmailSequenceStep = EmailSequenceStep.query.filter_by(
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr.id,
        active=True,
        overall_status=ProspectOverallStatus.PROSPECTED,
    ).first()
    if not sequence_intro:
        return False, "Sequence not configured correctly. Found no first message."
    sequence.append(
        {
            "seq_delay_details": {"delay_in_days": delay_days},
            "seq_number": 1,
            "subject": "{{Subject_Line}}",
            "email_body": "{{Body_1}}",
        }
    )
    delay_days = sequence_intro.sequence_delay_days

    sequence_accepted: EmailSequenceStep = EmailSequenceStep.query.filter_by(
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr.id,
        active=True,
        overall_status=ProspectOverallStatus.ACCEPTED,
    ).first()
    if sequence_accepted:
        sequence.append(
            {
                "seq_delay_details": {"delay_in_days": delay_days},
                "seq_number": 2,
                "subject": "",
                "email_body": "{{Body_2}}",
            }
        )
        delay_days = sequence_accepted.sequence_delay_days

    for i in range(1, 10):
        sequence_bumped: EmailSequenceStep = EmailSequenceStep.query.filter_by(
            client_archetype_id=archetype_id,
            client_sdr_id=client_sdr.id,
            active=True,
            overall_status=ProspectOverallStatus.BUMPED,
            bumped_count=i,
        ).first()
        if sequence_bumped:
            sequence.append(
                {
                    "seq_delay_details": {"delay_in_days": delay_days},
                    "seq_number": i + 2,
                    "subject": "",
                    "email_body": "{{Body_" + str(i + 2) + "}}",
                }
            )
            delay_days = sequence_bumped.sequence_delay_days
        else:
            break

    # 4. Get the current sequence and determine the length
    sl = Smartlead()
    current_sequence = sl.get_campaign_sequence_by_id(archetype.smartlead_campaign_id)
    current_sequence_length = len(current_sequence)

    # 5. If the sequence length is different, block from syncing
    if len(sequence) != current_sequence_length:
        return False, "Sequence length is different"

    # 6. Sync the sequence
    sl = Smartlead()
    result = sl.save_campaign_sequence(
        campaign_id=archetype.smartlead_campaign_id,
        sequences=sequence,
    )
    if not result.get("ok"):
        return False, result.get("error")

    return True, "Success"


def create_smartlead_campaign(
    archetype_id: int,
    sync_to_archetype: Optional[bool] = False,
) -> tuple[bool, str, int]:
    """Creates a Smartlead campaign for a given archetype

    Args:
        archetype_id (int): The ID of the archetype
        sync_to_archetype (Optional[bool], optional): Whether or not to sync the campaign ID to the archetype. Defaults to False.

    Returns:
        tuple[bool, str, int]: A tuple with the first value being True if successful, the second being a message, and the third being the ID of the Smartlead campaign
    """
    # 1. Get the Archetype, SDR
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return False, "Archetype not found", -1
    if archetype.smartlead_campaign_id:
        return False, "Campaign already exists", -1
    client_sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
    if not client_sdr:
        return False, "SDR not found", -1

    sl = Smartlead()

    # 2. Create the Smartlead campaign
    campaign_name = f"{client_sdr.name} (#{client_sdr.id}) - {archetype.archetype}"
    create_campaign_response = sl.create_campaign(campaign_name=campaign_name)
    if not create_campaign_response:
        return False, "Failed to create campaign", -1

    smartlead_campaign_id = create_campaign_response.get("id")
    if not smartlead_campaign_id:
        return False, "Failed to create campaign", -1

    # 2b. Update the general settings for tracking settings
    track_settings = []
    if (
        client_sdr.email_open_tracking_enabled is not None
        and not client_sdr.email_open_tracking_enabled
    ):
        track_settings.append("DONT_TRACK_EMAIL_OPEN")
    if (
        client_sdr.email_link_tracking_enabled is not None
        and not client_sdr.email_link_tracking_enabled
    ):
        track_settings.append("DONT_TRACK_LINK_CLICK")
    if len(track_settings) == 0:
        track_settings = None
    general_settings = {"track_settings": track_settings}
    sl.update_campaign_general_settings(
        campaign_id=smartlead_campaign_id,
        settings=general_settings,
    )

    # 3. Create the Smartlead campaign sequence, using the archetype's sequence
    delay_days = 0
    sequence = []

    # 3a. Get the PROSPECTED message
    sequence_intro: EmailSequenceStep = EmailSequenceStep.query.filter_by(
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr.id,
        active=True,
        overall_status=ProspectOverallStatus.PROSPECTED,
    ).first()
    if not sequence_intro:
        return False, "Sequence not configured correctly. Found no first message."
    sequence.append(
        {
            "seq_delay_details": {"delay_in_days": delay_days},
            "seq_number": 1,
            "subject": "{{Subject_Line}}",
            "email_body": "{{Body_1}}",
        }
    )
    delay_days = sequence_intro.sequence_delay_days

    # 3b. Get the ACCEPTED message
    sequence_accepted: EmailSequenceStep = EmailSequenceStep.query.filter_by(
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr.id,
        active=True,
        overall_status=ProspectOverallStatus.ACCEPTED,
    ).first()
    if sequence_accepted:
        sequence.append(
            {
                "seq_delay_details": {"delay_in_days": delay_days},
                "seq_number": 2,
                "subject": "",
                "email_body": "{{Body_2}}",
            }
        )
        delay_days = sequence_accepted.sequence_delay_days

    # 3c. Get the BUMPED messages
    for i in range(1, 10):
        sequence_bumped: EmailSequenceStep = EmailSequenceStep.query.filter_by(
            client_archetype_id=archetype_id,
            client_sdr_id=client_sdr.id,
            active=True,
            overall_status=ProspectOverallStatus.BUMPED,
            bumped_count=i,
        ).first()
        if sequence_bumped:
            sequence.append(
                {
                    "seq_delay_details": {"delay_in_days": delay_days},
                    "seq_number": i + 2,
                    "subject": "",
                    "email_body": "{{Body_" + str(i + 2) + "}}",
                }
            )
            delay_days = sequence_bumped.sequence_delay_days
        else:
            break

    sl.save_campaign_sequence(
        campaign_id=smartlead_campaign_id,
        sequences=sequence,
    )

    # 4. Add email accounts to the Smartlead campaign
    # 4a. Get the email accounts
    email_account_ids = []
    all_emails = sl.get_emails()
    offset = 0
    if len(all_emails) == 100:
        while len(all_emails) == 100:
            for email in all_emails:
                if email.get("from_name") == client_sdr.name:
                    warmup_details = email.get("warmup_details")
                    if (
                        warmup_details
                        and warmup_details.get("warmup_reputation") == "100%"
                    ):
                        email_account_ids.append(email.get("id"))
            offset += 100
            all_emails = sl.get_emails(offset=offset)
    else:
        for email in all_emails:
            if email.get("from_name") == client_sdr.name:
                warmup_details = email.get("warmup_details")
                if warmup_details and warmup_details.get("warmup_reputation") == "100%":
                    email_account_ids.append(email.get("id"))

    sl.add_email_account_to_campaign(
        campaign_id=smartlead_campaign_id,
        email_account_ids=email_account_ids,
    )

    # 5. Create the Smartlead campaign schedule
    campaign_schedule = {
        "timezone": client_sdr.timezone or "America/Los_Angeles",
        "days_of_the_week": [1, 2, 3, 4, 5],  # 1 is Monday, 7 is Sunday
        "start_hour": "09:00",
        "end_hour": "18:00",
        "min_time_btw_emails": 10,
        "max_new_leads_per_day": 10000,
        "schedule_start_time": datetime.datetime.now().isoformat(),
    }
    sl.update_campaign_schedule(
        campaign_id=smartlead_campaign_id,
        schedule=campaign_schedule,
    )

    # 6. Upload all webhooks into the campaign
    sl.add_all_campaign_webhooks(campaign_id=smartlead_campaign_id)

    # 7. Mark the campaign status as "START"
    sl.post_campaign_status(
        campaign_id=smartlead_campaign_id,
        status="START",
    )

    # 8. Optional - Sync the campaign ID to the archetype
    if sync_to_archetype:
        archetype.smartlead_campaign_id = smartlead_campaign_id
        db.session.commit()

    return True, "Success", smartlead_campaign_id


def update_smartlead_campaign_tracking_settings(
    campaign_id: int,
    track_open: Optional[bool] = None,
    track_link: Optional[bool] = None,
) -> bool:
    """Updates the tracking settings for a Smartlead campaign

    Args:
        campaign_id (int): The ID of the Smartlead campaign
        track_open (Optional[bool], optional): Whether or not to track email opens. Defaults to None.
        track_link (Optional[bool], optional): Whether or not to track link clicks. Defaults to None.

    Returns:
        bool: True if successful
    """
    # Update the Smartlead campaign
    sl = Smartlead()
    track_settings = []
    if track_open is not None and not track_open:
        track_settings.append("DONT_TRACK_EMAIL_OPEN")
    if track_open is not None and not track_link:
        track_settings.append("DONT_TRACK_LINK_CLICK")
    if len(track_settings) == 0:
        track_settings = None

    general_settings = {"track_settings": track_settings}
    result = sl.update_campaign_general_settings(
        campaign_id=campaign_id,
        settings=general_settings,
    )
    success = result.get("ok")

    # Update the ClientArchetype
    if success:
        archetypes: List[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.smartlead_campaign_id == campaign_id,
        ).all()
        for archetype in archetypes:
            archetype.email_open_tracking_enabled = track_open
            archetype.email_link_tracking_enabled = track_link
        db.session.commit()

    return success


def set_campaign_id(archetype_id: int, campaign_id: int) -> bool:
    """Sets the Smartlead campaign ID for a given archetype

    Args:
        archetype_id (int): ID of the archetype
        campaign_id (int): ID of the Smartlead campaign

    Returns:
        bool: True if successful
    """
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    archetype.smartlead_campaign_id = campaign_id
    db.session.commit()

    return True


def get_campaign_sequence_by_id(campaign_id: int) -> list[dict]:
    """Gets the sequence of a Smartlead campaign

    Args:
        campaign_id (int): ID of the Smartlead campaign

    Returns:
        dict: The sequence of the Smartlead campaign
    """
    sl = Smartlead()
    sequence = sl.get_campaign_sequence_by_id(campaign_id)

    return sequence


@celery.task
def sync_all_campaign_leads() -> bool:
    """Syncs all leads in all campaigns with the corresponding prospects, for all SDRs

    Returns:
        bool: True if successful
    """
    # Get all active SDRs
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True,
    )

    for sdr in sdrs:
        sync_campaign_leads_for_sdr.delay(client_sdr_id=sdr.id)

    return True


@celery.task
def sync_campaign_leads_for_sdr(client_sdr_id: int) -> bool:
    """Syncs all leads in a campaign with the corresponding prospects, for a given SDR

    Args:
        client_sdr_id (int): The ID of the SDR

    Raises:
        Exception: If no smartlead campaign ID is found for the SDR

    Returns:
        bool: True if successful
    """

    from src.automation.orchestrator import add_process_to_queue

    archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.active == True,
    ).all()

    for archetype in archetypes:
        if archetype.smartlead_campaign_id == None:
            continue

        sl = Smartlead()
        statistics = sl.get_campaign_statistics_by_id(archetype.smartlead_campaign_id)
        statistics = statistics.get("data")
        if not statistics:
            raise Exception("No smartlead campaign statistics found")

        for lead in statistics:
            # sync_prospect_with_lead(
            #     client_id=archetype.client_id,
            #     archetype_id=archetype.id,
            #     client_sdr_id=client_sdr_id,
            #     lead=lead,
            # )
            args = {
                "client_id": archetype.client_id,
                "archetype_id": archetype.id,
                "client_sdr_id": client_sdr_id,
                "lead": lead,
            }
            add_process_to_queue(
                type="sync_prospect_with_lead",
                meta_data={"args": args},
                execution_date=datetime.datetime.utcnow(),
                commit=True,
            )


@celery.task
def sync_prospect_with_lead(
    client_id: int, archetype_id: int, client_sdr_id: int, lead: dict
) -> tuple[bool, str]:
    """Syncs a prospect with a lead from a Smartlead campaign

    Args:
        client_id (int): Not used. Only for Celery
        archetype_id (int): Not used. Only for Celery
        client_sdr_id (int): The ID of the SDR
        lead (dict): The lead from the Smartlead campaign, which is a SmartleadCampaignStatisticEntry object

    Returns:
        tuple[bool, str]: A tuple with the first value being True if successful, and the second being a message
    """
    # 0. Turn the lead into a SmartleadCampaignStatisticEntry object
    lead: SmartleadCampaignStatisticEntry = SmartleadCampaignStatisticEntry(**lead)

    # 1. Try to find the prospect by email. If not found, return False
    prospect: Prospect = Prospect.query.filter(
        Prospect.email == lead.lead_email,
        Prospect.client_sdr_id == client_sdr_id,
    ).first()
    if not prospect:
        print(f"Prospect not found: {lead.lead_email}")
        return False, "Prospect not found"

    # 2. Get the corresponding prospect email. If not found, create a new one
    prospect_email_id = prospect.approved_prospect_email_id
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    if not prospect_email:
        # Create a new prospect email
        prospect_email: ProspectEmail = ProspectEmail(
            prospect_id=prospect.id,
            email_status=ProspectEmailStatus.APPROVED,
            outreach_status=ProspectEmailOutreachStatus.NOT_SENT,
        )
        db.session.add(prospect_email)
        db.session.commit()

        prospect.approved_prospect_email_id = prospect_email.id
        prospect_email_id = prospect_email.id
        db.session.commit()
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)

    # 3a. If the lead was sent an email and had previously not, update the prospect email status
    if (
        lead.sent_time
        and prospect_email.outreach_status == ProspectEmailOutreachStatus.NOT_SENT
    ):
        print('Updating prospect email status to "SENT_OUTREACH"')
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.SENT_OUTREACH,
            # custom_webhook_urls=[URL_MAP["ops-email-notifications"]],
        )

    # 3b. If the lead has opened the email and had previously not, update the prospect email status
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    if (
        lead.open_time
        and prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    ):
        print('Updating prospect email status to "EMAIL_OPENED"')
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.EMAIL_OPENED,
            # custom_webhook_urls=[URL_MAP["ops-email-notifications"]],
        )

    # 3c. Special case: Lead has replied to the email, and the lead has replied before, we need to check for new message
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    if lead.reply_time and (
        prospect_email.outreach_status == ProspectEmailOutreachStatus.SCHEDULING
        or prospect_email.outreach_status == ProspectEmailOutreachStatus.ACTIVE_CONVO
        or prospect_email.outreach_status == ProspectEmailOutreachStatus.DEMO_SET
        or prospect_email.outreach_status == ProspectEmailOutreachStatus.DEMO_WON
        or prospect_email.outreach_status == ProspectEmailOutreachStatus.DEMO_LOST
    ):
        print("Checking for new reply from prospect")
        # 3c.1. Get the latest reply
        sl = Smartlead()
        lead_data = sl.get_lead_by_email_address(lead.lead_email)
        lead_id = lead_data["id"]
        archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
        message_history = sl.get_message_history_using_lead_and_campaign_id(
            lead_id=lead_id, campaign_id=archetype.smartlead_campaign_id
        )
        history = message_history["history"]
        prospect_message: str = None
        for item in reversed(history):
            if item["type"] == "REPLY":
                sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
                # 3c.2. Determine if the reply is new
                time = item["time"]
                time = convert_string_to_datetime_or_none(content=time)
                time = time.replace(tzinfo=pytz.UTC)
                last_reply_time = (
                    prospect_email.last_reply_time.replace(tzinfo=pytz.UTC)
                    if prospect_email.last_reply_time
                    else None
                )
                if not last_reply_time or time > last_reply_time:
                    prospect_email.last_reply_time = time
                    prospect_email.hidden_until = None
                    db.session.commit()

                    # Beautify the email body
                    prospect_message = item["email_body"]
                    prospect_message = prospect_message.replace("<br>", "\n")
                    bs = BeautifulSoup(prospect_message, "html.parser")
                    remove_past_convo = bs.find("div", {"class": "gmail_quote"})
                    if remove_past_convo:
                        remove_past_convo.decompose()
                    prospect_message = bs.get_text()
                    prospect_message = prospect_message[:150] + "..."
                    prospect_message = re.sub("\n+", "\n", prospect_message)
                    prospect_message = prospect_message.strip("\n")

                    send_slack_message(
                        message="SellScale AI just received a new reply from prospect!",
                        webhook_urls=[URL_MAP["eng-sandbox"]],
                        blocks=[
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"{prospect.full_name} just sent a new reply on Email",
                                },
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "*{prospect_first_name}*:\n>{prospect_message}".format(
                                        prospect_first_name=prospect.first_name,
                                        prospect_message=prospect_message[:150],
                                    ),
                                },
                            },
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "plain_text",
                                        "text": "🎯 Campaign: "
                                        + str(archetype.archetype),
                                    },
                                    {
                                        "type": "plain_text",
                                        "text": "🧳 Title: "
                                        + str(prospect.title)
                                        + " @ "
                                        + str(prospect.company)[0:20]
                                        + ("..." if len(prospect.company) > 20 else ""),
                                        "emoji": True,
                                    },
                                    {
                                        "type": "plain_text",
                                        "text": "📌 SDR: " + sdr.name,
                                        "emoji": True,
                                    },
                                ],
                            },
                        ],
                    )
            break

    # 3d. If the lead has replied to the email and had previously not, update the prospect email status
    if lead.reply_time and (
        prospect_email.outreach_status == ProspectEmailOutreachStatus.EMAIL_OPENED
        or prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    ):
        # 3d.1. Get the prospect's message
        sl = Smartlead()
        lead_data = sl.get_lead_by_email_address(lead.lead_email)
        lead_id = lead_data["id"]
        archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
        message_history = sl.get_message_history_using_lead_and_campaign_id(
            lead_id=lead_id, campaign_id=archetype.smartlead_campaign_id
        )
        history = message_history["history"]
        prospect_message: str = None
        for item in history:
            if item["type"] == "REPLY":
                prospect_message = item["email_body"]
                prospect_message_newlined = prospect_message.replace("<br>", "\n")
                bs = BeautifulSoup(prospect_message_newlined, "html.parser")
                remove_past_convo = bs.find("div", {"class": "gmail_quote"})
                if remove_past_convo:
                    remove_past_convo.decompose()
                prospect_message_newlined = bs.get_text()
                prospect_message = prospect_message_newlined[:150] + "..."
                prospect_message = re.sub("\n+", "\n", prospect_message)
                prospect_message = prospect_message.strip("\n")
                reply_time = item["time"]
                reply_time = convert_string_to_datetime_or_none(content=reply_time)
                break

        # 3d.2. Get the sent message
        sent_message = lead.email_message
        bs = BeautifulSoup(lead.email_message, "html.parser")
        remove_past_convo = bs.find("div", {"class": "gmail_quote"})
        if remove_past_convo:
            remove_past_convo.decompose()
        sent_message = bs.get_text()
        sent_message = sent_message[:150] + "..."

        metadata = {
            "prospect_email": lead.lead_email,
            "email_sent_subject": lead.email_subject,
            "email_sent_body": sent_message,
            "email_reply_body": prospect_message,
        }
        print('Updating prospect email status to "ACTIVE_CONVO"')
        if prospect_email.outreach_status == ProspectEmailOutreachStatus.EMAIL_OPENED:
            update_prospect_status_email(
                prospect_id=prospect.id,
                new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                # custom_webhook_urls=[URL_MAP["ops-email-notifications"]],
                metadata=metadata,
            )
        elif (
            prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
        ):
            # TODO: One day, we may use smartlead's behavior with OOOs having a reply_time but no open_time to create OOO special behavior
            # For now, we'll just mark it as EMAIL_OPENED, and then ACTIVE_CONVO
            update_prospect_status_email(
                prospect_id=prospect.id,
                new_status=ProspectEmailOutreachStatus.EMAIL_OPENED,
                # custom_webhook_urls=[URL_MAP["ops-email-notifications"]],
            )
            update_prospect_status_email(
                prospect_id=prospect.id,
                new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                # custom_webhook_urls=[URL_MAP["ops-email-notifications"]],
                metadata=metadata,
            )

        prospect_email.last_reply_time = reply_time
        db.session.commit()

    print(f"Actions finished for: {prospect.email}")
    return True, "Success"


@celery.task
def upload_prospect_to_campaign(prospect_id: int) -> tuple[bool, int]:
    """Uploads a single prospect to a Smartlead campaign using `sl.add_leads_to_campaign_by_id`

    ASSUMPTIONS:
    - The prospect has an approved email
    - The prospect has a schedule with messages fully generated

    Args:
        prospect_id (int): The ID of the prospect

    Returns:
        tuple[bool, int]: A tuple with the first value being True if successful, and the second being the number of prospects uploaded
    """
    # LOGGER (delete me eventually): We need to log that we are going to upload now
    log: ProspectInSmartlead = ProspectInSmartlead.query.filter(
        ProspectInSmartlead.prospect_id == prospect_id
    ).first()
    if log:
        log.log.append(
            f"upload_prospect_to_campaign ({datetime.datetime.utcnow()}): Starting to upload Prospect to Campaign"
        )
        flag_modified(log, "log")
        db.session.commit()

    # Get the prospect, archetype, and smartlead campaign ID
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return False, "Prospect not found"
    if not prospect.approved_prospect_email_id:
        return False, "Prospect does not have an approved email"
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    if archetype.smartlead_campaign_id == None:
        return False, "No Smartlead campaign ID found"

    # Get the message schedule
    schedule: list[EmailMessagingSchedule] = (
        EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.prospect_email_id
            == prospect.approved_prospect_email_id
        )
        .order_by(EmailMessagingSchedule.id.asc())
        .all()
    )
    if not schedule:
        return False, "No messaging schedule found"
    for message in schedule:
        if not message.subject_line_id:
            return (
                False,
                "Messaging schedule not fully generated. Subject Line missing.",
            )
        if not message.body_id:
            return False, "Messaging schedule not fully generated. Email Body missing."

    # Create the lead list
    custom_fields = {}
    for index, message in enumerate(schedule):
        message: EmailMessagingSchedule = message
        if message.email_type == EmailMessagingType.INITIAL_EMAIL:
            subject_line: GeneratedMessage = GeneratedMessage.query.get(
                message.subject_line_id
            )
            body: GeneratedMessage = GeneratedMessage.query.get(message.body_id)
            custom_fields["Subject_Line"] = subject_line.completion
            custom_fields[f"Body_1"] = body.completion
        if message.email_type == EmailMessagingType.FOLLOW_UP_EMAIL:
            email_body: GeneratedMessage = GeneratedMessage.query.get(message.body_id)
            custom_fields[f"Body_{index+1}"] = email_body.completion

    # Add the prospect to the campaign
    sl = Smartlead()
    result = sl.add_campaign_leads(
        campaign_id=archetype.smartlead_campaign_id,
        leads=[
            {
                "email": prospect.email,
                "custom_fields": custom_fields,
            }
        ],
    )

    # Log the result
    if log:
        log.log.append(
            f"upload_prospect_to_campaign ({datetime.datetime.utcnow()}): Smartlead Upload Result: {result}"
        )
        flag_modified(log, "log")
        db.session.commit()

    # If not all prospects were uploaded, send a slack message
    if (result.get("upload_count") != result.get("total_leads")) and (
        result.get("upload_count") != result.get("already_added_to_campaign")
    ):
        send_slack_message(
            message=f"Only {result.get('upload_count')} of {result.get('total_leads')} prospects were uploaded to Smartlead campaign from {archetype.archetype} (#{archetype.id})",
            webhook_urls=[URL_MAP["eng-sandbox"]],
        )
        return False, "Not all prospects were uploaded"

    send_slack_message(
        message=f"Uploaded 1 prospect {prospect.full_name}#{prospect.id} to Smartlead campaign from {archetype.archetype} (#{archetype.id})",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    if log:
        log.log.append(
            f"upload_prospect_to_campaign ({datetime.datetime.utcnow()}): Finished uploading. Will now verify"
        )
        flag_modified(log, "log")
        db.session.commit()

    exists = prospect_exists_in_smartlead(prospect_id=prospect.id)
    if exists:
        log.in_smartlead = True
        log.log.append(
            f"SUCCESS -- upload_prospect_to_campaign ({datetime.datetime.utcnow()}): Verified that Prospect is in Smartlead."
        )
        flag_modified(log, "log")
    else:
        log.in_smartlead = False
        log.log.append(
            f"FAILED -- upload_prospect_to_campaing ({datetime.datetime.utcnow()}): Could not verify that Prospect is in Smartlead."
        )
        flag_modified(log, "log")
    db.session.commit()

    # Update the Prospect Status
    update_prospect_status_email(
        prospect_id=prospect.id,
        new_status=ProspectEmailOutreachStatus.QUEUED_FOR_OUTREACH,
    )

    return True, 1


def generate_smart_email_response(
    client_sdr_id: int,
    prospect_id: int,
    conversation: Optional[list[dict]] = [],
) -> str:
    """Generates a smart email response based on the conversation transcript provided

    Args:
        client_sdr_id (int): The ID of the SDR
        prospect_id (int): The ID of the prospect
        conversation (Optional[list[dict]], optional): The conversation transcript. Defaults to [].

    Returns:
        str: The generated email response
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(sdr.client_id)

    if not conversation:
        conversation = get_message_history_for_prospect(
            prospect_id=prospect_id,
        )

    convo = ""
    for message in conversation:
        if message.get("type") == "SENT":
            convo += f"{sdr.name}: {message.get('email_body')}\n"
        else:
            convo += f"{prospect.full_name}: {message.get('email_body')}\n"

    prompt = f"""
    You are a Sales assistant helping write follow up email copy for me.

## Here is information about my company:
My Name: {sdr.name}
Company: {client.company}
Tagline: {client.tagline}

## Here is who I am emailing:
Prospect: {prospect.full_name}
Prospect Company: {prospect.company}
Prospect Title: {prospect.title}

## Important notes:
- Please use markdown to format your response.
- Keep the follow up concise. Each message should be no longer than a message in the conversation transcript.

## Here is the conversation transcript:

{convo}

## What is an appropriate follow up response based on the context and transcript provided?

{sdr.name}:
    """

    response = get_text_generation(
        [{"role": "user", "content": prompt}],
        prospect_id=prospect_id,
        client_sdr_id=client_sdr_id,
        max_tokens=2000,
        model="gpt-4",
        type="EMAIL",
    )

    html_response = markdown.markdown(response)

    create_email_automated_reply_entry(
        prospect_id=prospect_id,
        client_sdr_id=client_sdr_id,
        prompt=prompt,
        email_body=html_response,
    )

    return html_response


def sync_workmail_to_smartlead(
    client_sdr_id: int,
    username: str,
    email: str,
    password: str,
    emails_per_day: int = 5,
) -> tuple:
    """Syncs a WorkMail account to Smartlead

    Args:
        client_sdr_id (int): The ID of the SDR
        username (str): The username of the WorkMail account
        email (str): The email of the SDR
        password (str): The password of the SDR
        emails_per_day (int, optional): The number of emails to send per day. Defaults to 30.

    Returns:
        tuple: A tuple with the first value being True if successful, and the second being the message, and the third being the email account ID
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Create the Smartlead email account
    sl = Smartlead()
    result = sl.create_email_account(
        {
            "id": None,  # set null to create new email account
            "from_name": sdr.name,  # DO NOT CHANGE
            "from_email": email,  # DO NOT CHANGE
            "user_name": username,  # DO NOT CHANGE
            "password": password,  # DO NOT CHANGE
            "smtp_host": "smtp.mail.us-east-1.awsapps.com",
            "smtp_port": 465,
            "imap_host": "imap.mail.us-east-1.awsapps.com",
            "imap_port": 993,
            "max_email_per_day": emails_per_day,
            "custom_tracking_url": "",
            "bcc": "",
            "signature": "",
            "warmup_enabled": True,
            "total_warmup_per_day": 30,
            "daily_rampup": 5,
            "reply_rate_percentage": 20,
            "client_id": None,  # set value to assign to client id
        }
    )

    if result.get("ok", False):
        send_slack_message(
            message="Smartlead Account Setup",
            webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"""🦑 New Account Created on Smartlead: {email}
Warming: {emails_per_day} / day
Volume: 2 / day""",
                    },
                }
            ],
        )

    email_account_id = result.get("emailAccountId")

    return result.get("ok", False), result.get("message", ""), email_account_id


def smartlead_deactivate_email_account(email_account_id: str):
    sl = Smartlead()
    result = sl.deactivate_email_account(email_account_id)

    print(result)

    if result.get("ok", False):
        send_slack_message(
            message="Smartlead Account Deactivated",
            webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"""🦑 Account Deactivated on Smartlead: {email_account_id}""",
                    },
                }
            ],
        )

    return result.get("ok", False)


def smartlead_update_prospect_status(
    prospect_id: int,
    new_status: ProspectOverallStatus,
) -> tuple[bool, str]:
    """If the prospect is part of Smartlead, updates the prospect's status in Smartlead

    Args:
        prospect_id (int): The ID of the prospect
        new_status (ProspectOverallStatus): The new status of the prospect

    Returns:
        tuple[bool, str]: A tuple with the first value being True if successful, and the second being a message
    """
    # Get the prospect and archetype
    prospect: Prospect = Prospect.query.get(prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    if not archetype.smartlead_campaign_id:
        return False, "No Smartlead campaign ID found"

    # If the new status REMOVED, then update
    if new_status == ProspectOverallStatus.REMOVED:
        sl = Smartlead()
        lead = sl.get_lead_by_email_address(prospect.email)
        if not lead:
            return False, "Lead not found"
        lead_id = lead["id"]
        result = sl.post_update_lead_category(
            campaign_id=archetype.smartlead_campaign_id,
            lead_id=lead_id,
            category_id=sl.LEAD_CATEGORIES.get("Do Not Contact"),
        )
        if not result.get("ok"):
            return False, "Failed to update lead category"

        send_slack_message(
            message=f"SMARTLEAD: Moved prospect {prospect.full_name}#{prospect.id} to DO NOT CONTACT",
            webhook_urls=[URL_MAP["eng-sandbox"]],
        )

    # If the new status ACTIVE_CONVO, then update
    if new_status == ProspectOverallStatus.ACTIVE_CONVO:
        sl = Smartlead()
        lead = sl.get_lead_by_email_address(prospect.email)
        if not lead:
            return False, "Lead not found"
        lead_id = lead["id"]
        result = sl.post_update_lead_category(
            campaign_id=archetype.smartlead_campaign_id,
            lead_id=lead_id,
            category_id=sl.LEAD_CATEGORIES.get(
                "Do Not Contact"
            ),  # We make this Do Not Contact for now, but we can change this later
        )
        if not result.get("ok"):
            return False, "Failed to update lead category"

    return True, "Success"


def toggle_email_account_for_archetype(
    archetype_id: int, email_account_ids: list[str], enable: bool
) -> tuple[bool, str]:
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype.smartlead_campaign_id:
        return False, "No Smartlead campaign ID found"

    sl = Smartlead()

    if enable:
        result = sl.add_email_account_to_campaign(
            campaign_id=archetype.smartlead_campaign_id,
            email_account_ids=email_account_ids,
        )
    else:
        result = sl.remove_email_account_from_campaign(
            campaign_id=archetype.smartlead_campaign_id,
            email_account_ids=email_account_ids,
        )

    return result.get("ok", False), result.get("message", "")


def prospect_exists_in_smartlead(prospect_id: int) -> bool:
    """Verifies that a prospect exists in Smartlead

    Args:
        prospect_id (int): The ID of the prospect

    Returns:
        bool: True if the prospect exists in Smartlead
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    if not archetype.smartlead_campaign_id:
        return False

    # Get the lead information
    sl = Smartlead()
    lead = sl.get_lead_by_email_address(prospect.email)
    if not lead:
        return False

    # Verify that the campaign is correct (we can sometimes have same leads in diff campaigns, but we want to make sure we're looking at the right one)
    lead_campaign_data = lead.get("lead_campaign_data")
    if not lead_campaign_data or len(lead_campaign_data) == 0:
        return False

    # If it is in the campaign, return True
    for entry in lead_campaign_data:
        if entry.get("campaign_id") == archetype.smartlead_campaign_id:
            return True

    return False


def find_prospect_in_smartlead(prospect_id: int) -> dict:
    """Finds a prospect in Smartlead

    Args:
        prospect_id (int): The ID of the prospect

    Returns:
        dict: The prospect in Smartlead
    """
    prospect: Prospect = Prospect.query.get(prospect_id)

    sl = Smartlead()
    lead = sl.get_lead_by_email_address(prospect.email)

    return lead
