import datetime
import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from src.utils.datetime.dateparse_utils import (
    convert_string_to_datetime,
    convert_string_to_datetime_or_none,
)

from src.utils.lists import chunk_list

from src.prospecting.services import update_prospect_status_email

from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.prospecting.models import Prospect

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
	a.smartlead_campaign_id
FROM
	prospect p
	LEFT JOIN prospect_email pe ON p.approved_prospect_email_id = pe.id
	LEFT JOIN client_archetype a ON p.archetype_id = a.id
WHERE
	pe.outreach_status = 'ACTIVE_CONVO'
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
            }
        )

    snoozed_query = f"""SELECT
	p.id,
    p.full_name,
    p.title,
    p.img_url,
    p.icp_fit_score,
	a.smartlead_campaign_id,
    pe.hidden_until
FROM
	prospect p
	LEFT JOIN prospect_email pe ON p.approved_prospect_email_id = pe.id
	LEFT JOIN client_archetype a ON p.archetype_id = a.id
WHERE
	pe.outreach_status = 'ACTIVE_CONVO'
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
            }
        )

        demo_query = f"""SELECT
	p.id,
    p.full_name,
    p.title,
    p.img_url,
    p.icp_fit_score,
	a.smartlead_campaign_id
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
            }
        )

    return {
        "inbox": replied_prospects,
        "snoozed": snoozed_prospects,
        "demo": demo_prospects,
    }


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


def reply_to_prospect(prospect_id: int, email_body: str) -> bool:
    """Replies to a prospect via Smartlead

    Args:
        prospect_id (int): The ID of the prospect
        email_body (str): The body of the email

    Returns:
        bool: True if successful
    """
    # Get the prospect, archetype, and smartlead campaign ID
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
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

    # Send the reply
    response = sl.reply_to_lead(
        campaign_id=campaign_id,
        email_stats_id=stats_id,
        email_body=email_body,
        reply_message_id=reply_message_id,
        reply_email_time=reply_email_time,
        reply_email_body=reply_email_body,
    )
    if not response:
        return False

    # SLACK NOTIFICATION
    # Get the pretty email body
    reply_email_body = reply_email_body.replace("<br>", "\n")
    bs = BeautifulSoup(reply_email_body, "html.parser")
    remove_past_convo = bs.find("div", {"class": "gmail_quote"})
    if remove_past_convo:
        remove_past_convo.decompose()
    reply_email_body = bs.get_text()

    # Get the pretty reply
    message = email_body.replace("<br>", "\n")
    bs = BeautifulSoup(message, "html.parser")
    remove_past_convo = bs.find("div", {"class": "gmail_quote"})
    if remove_past_convo:
        remove_past_convo.decompose()
    message = bs.get_text()

    webhook_urls: List[str] = []
    client: Client = Client.query.get(prospect.client_id)
    webhook_urls.append(client.pipeline_notifications_webhook_url)

    # Send the Slack message
    send_slack_message(
        message="SellScale AI just replied to prospect!",
        webhook_urls=webhook_urls,
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💬 SellScale AI just replied to "
                    + prospect.full_name
                    + " on Email",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": '*{prospect_first_name}*:\n_"{prospect_message}"_\n\n*{first_name} (AI)*:\n_"{ai_response}"_'.format(
                        prospect_first_name=prospect.first_name,
                        prospect_message=reply_email_body[:150],
                        ai_response=message[:150],
                        first_name=client_sdr.name.split(" ")[0],
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "🧳 Title: "
                        + str(prospect.title)
                        + " @ "
                        + str(prospect.company)[0:20]
                        + ("..." if len(prospect.company) > 20 else ""),
                        "emoji": True,
                    },
                    # {
                    #     "type": "plain_text",
                    #     "text": "🪜 Status: "
                    #     + prospect.status.value.replace("_", " ").lower(),
                    #     "emoji": True,
                    # },
                    {
                        "type": "plain_text",
                        "text": "📌 SDR: " + client_sdr.name,
                        "emoji": True,
                    },
                ],
            },
            # {
            #     "type": "section",
            #     "block_id": "sectionBlockWithLinkButton",
            #     "text": {"type": "mrkdwn", "text": "View Conversation in Sight"},
            #     "accessory": {
            #         "type": "button",
            #         "text": {
            #             "type": "plain_text",
            #             "text": "View Convo",
            #             "emoji": True,
            #         },
            #         "value": direct_link,
            #         "url": direct_link,
            #         "action_id": "button-action",
            #     },
            # },
        ],
    )

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
    warmings = sl.get_emails()

    # If a client SDR ID is provided, filter out all warmings that are not for that SDR
    if client_sdr_id:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        warmings = [
            warming
            for warming in warmings
            if warming.get("from_name") == client_sdr.name
        ]

    return warmings


def get_warmup_percentage(sent_count: int) -> int:
    TOTAL_SENT = 180

    return min(round((sent_count / TOTAL_SENT) * 100, 0), 100)


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
                if (
                    not prospect_email.last_reply_time
                    or time > prospect_email.last_reply_time
                ):
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
            "email_title": lead.email_subject,
            "email_snippet": sent_message,
            "prospect_message": prospect_message,
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


def sync_prospects_to_campaign(client_sdr_id: int, archetype_id: int):
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype.smartlead_campaign_id == None:
        return

    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == archetype_id
    ).all()

    sl = Smartlead()

    leads = sl.get_leads_export(archetype.smartlead_campaign_id)
    # Filter out all prospects that are already in the campaign
    prospects = [
        prospect
        for prospect in prospects
        if prospect.email not in [lead.get("email") for lead in leads]
    ]

    prospect_chunks = chunk_list(
        prospects, 100
    )  # max 100 leads can be added at a time with API
    for chunk in prospect_chunks:
        result = sl.add_campaign_leads(
            campaign_id=archetype.smartlead_campaign_id,
            leads=[
                Lead(
                    first_name=prospect.first_name,
                    last_name=prospect.last_name,
                    email=prospect.email,
                    phone_number=None,
                    company_name=prospect.company,
                    website=None,
                    location=None,
                    custom_fields={"source": "SellScale"},
                    linkedin_profile=prospect.linkedin_url,
                    company_url=prospect.company_url,
                )
                for prospect in chunk
            ],
        )
        # print(result)

    send_slack_message(
        message=f"Imported {len(prospects)} prospects to Smartlead campaign from {archetype.archetype} (#{archetype.id})",
        webhook_urls=[URL_MAP["ops-outbound-warming"]],
    )

    return True, len(prospects)
