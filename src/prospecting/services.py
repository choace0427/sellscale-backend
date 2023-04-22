from datetime import datetime
from typing import Optional
from src.email_outbound.models import EmailConversationThread, EmailConversationMessage
from sqlalchemy import or_
import requests
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords,
    VALID_UPDATE_EMAIL_STATUS_MAP,
)
from src.client.models import Client, ClientArchetype, ClientSDR
from src.research.linkedin.services import research_personal_profile_details
from src.research.services import create_iscraper_payload_cache
from src.prospecting.models import (
    Prospect,
    ProspectChannels,
    ProspectStatus,
    ProspectUploadBatch,
    ProspectNote,
    ProspectOverallStatus,
    ProspectHiddenReason,
    VALID_NEXT_LINKEDIN_STATUSES,
)
from app import db, celery
from src.utils.abstract.attr_utils import deep_get
from src.utils.random_string import generate_random_alphanumeric
from src.utils.slack import send_slack_message
from src.utils.converters.string_converters import (
    get_last_name_from_full_name,
    get_first_name_from_full_name,
)
from model_import import (
    LinkedinConversationEntry,
    IScraperPayloadCache,
    IScraperPayloadType,
    OutboundCampaignStatus,
)
from src.research.linkedin.iscraper_model import IScraperExtractorTransformer
from src.automation.slack_notification import send_status_change_slack_block
from src.utils.converters.string_converters import needs_title_casing
import datetime

def search_prospects(
    query: str, client_id: int, client_sdr_id: int, limit: int = 10, offset: int = 0
):
    """Search prospects by full name, company, or title

    Args:
        query (str): Search query
        limit (int, optional): The number of results to return. Defaults to 10.
        offset (int, optional): The offset to start from. Defaults to 0.

    Returns:
        list[Prospect]: List of prospects
    """
    lowered_query = query.lower()
    prospects = (
        Prospect.query.filter(
            Prospect.client_id == client_id,
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.full_name.ilike(f"%{lowered_query}%")
            | Prospect.company.ilike(f"%{lowered_query}%")
            | Prospect.email.ilike(f"%{lowered_query}%")
            | Prospect.linkedin_url.ilike(f"%{lowered_query}%"),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )
    return prospects


def get_prospects(
    client_sdr_id: int,
    query: str = "",
    channel: str = ProspectChannels.LINKEDIN.value,
    status: list[str] = None,
    persona_id: int = -1,
    limit: int = 50,
    offset: int = 0,
    ordering: list[dict[str, int]] = [],
) -> dict[int, list[Prospect]]:
    """Gets prospects belonging to the SDR, with optional query and ordering.

    Authorization required.

    Args:
        client_sdr_id (int): ID of the SDR, supplied by the require_user decorator
        query (str, optional): Query. Defaults to "".
        channel (str, optional): Channel to filter by. Defaults to ProspectChannels.SELLSCALE.value.
        status (list[str], optional): List of statuses to filter by. Defaults to None.
        persona_id (int, optional): Persona ID to filter by. Defaults to -1.
        limit (int, optional): Number of records to return. Defaults to 50.
        offset (int, optional): The offset to start returning from. Defaults to 0.
        ordering (list, optional): Ordering to apply. See below. Defaults to [].

    Ordering logic is as follows
        The ordering list should have the following tuples:
            - full_name: 1 or -1, indicating ascending or descending order
            - company: 1 or -1, indicating ascending or descending order
            - status: 1 or -1, indicating ascending or descending order
            - last_updated: 1 or -1, indicating ascending or descending order
            - icp_fit_score: 1 or -1, indicating ascending or descending order
        The query will be ordered by these fields in the order provided
    """
    # Make sure that the provided status is in the channel's status enum
    if status:
        channel_statuses = ProspectChannels.map_to_other_channel_enum(
            channel
        )._member_names_
        for s in status:
            if s not in channel_statuses:
                raise ValueError(
                    f"Invalid status '{s}' provided for channel '{channel}'"
                )

    # Construct ordering array
    ordering_arr = []
    for order in ordering:
        order_name = order.get("field")
        order_direction = order.get("direction")
        if order_name == "full_name":
            if order_direction == 1:
                ordering_arr.append(Prospect.full_name.asc())
            elif order_direction == -1:
                ordering_arr.append(Prospect.full_name.desc())
        elif order_name == "company":
            if order_direction == 1:
                ordering_arr.append(Prospect.company.asc())
            elif order_direction == -1:
                ordering_arr.append(Prospect.company.desc())
        elif order_name == "status":
            if order_direction == 1:
                ordering_arr.append(Prospect.status.asc())
            elif order_direction == -1:
                ordering_arr.append(Prospect.status.desc())
        elif order_name == "last_updated":
            if order_direction == 1:
                ordering_arr.append(Prospect.updated_at.asc())
            elif order_direction == -1:
                ordering_arr.append(Prospect.updated_at.desc())
        elif order_name == "icp_fit_score":
            if order_direction == 1:
                ordering_arr.append(Prospect.icp_fit_score.asc())
            elif order_direction == -1:
                ordering_arr.append(Prospect.icp_fit_score.desc())

    # Pad ordering array with None values, set to number of ordering options: 4
    while len(ordering_arr) < 4:
        ordering_arr.insert(0, None)

    # Set status filter.
    filtered_status = status
    if status is None:
        if channel == ProspectChannels.LINKEDIN.value:  # LinkedIn page
            filtered_status = ProspectStatus.all_statuses()
        elif channel == ProspectChannels.EMAIL.value:  # Email page
            filtered_status = ProspectEmailOutreachStatus.all_statuses()
        else:  # Overall page
            filtered_status = ProspectOverallStatus.all_statuses()

    # Set the channel filter
    if channel == ProspectChannels.LINKEDIN.value:
        filtered_channel = Prospect.status
    elif channel == ProspectChannels.SELLSCALE.value:
        filtered_channel = Prospect.overall_status
    elif channel == ProspectChannels.EMAIL.value:
        filtered_channel = ProspectEmail.outreach_status

    # Construct top query
    prospects = Prospect.query
    if (
        channel == ProspectChannels.EMAIL.value
    ):  # Join to ProspectEmail if filtering by email
        prospects = prospects.join(
            ProspectEmail, Prospect.id == ProspectEmail.prospect_id, isouter=True
        )

    # Apply filters
    prospects = (
        prospects.filter(filtered_channel.in_(filtered_status))
        .filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.full_name.ilike(f"%{query}%")
            | Prospect.company.ilike(f"%{query}%")
            | Prospect.email.ilike(f"%{query}%")
            | Prospect.linkedin_url.ilike(f"%{query}%"),
        )
        .order_by(ordering_arr[0])
        .order_by(ordering_arr[1])
        .order_by(ordering_arr[2])
        .order_by(ordering_arr[3])
    )
    if persona_id != -1:
        prospects = prospects.filter(Prospect.archetype_id == persona_id)
    total_count = prospects.count()
    prospects = prospects.limit(limit).offset(offset).all()
    return {"total_count": total_count, "prospects": prospects}


def nylas_get_threads(client_sdr_id: int, prospect: Prospect, limit: int):

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    res = requests.get(f'https://api.nylas.com/threads?limit={limit}&any_email={prospect.email}', headers = {"Authorization": f'Bearer {client_sdr.nylas_auth_code}'})
    result = res.json()

    for thread in result:
      existing_thread = EmailConversationThread.query.filter_by(nylas_thread_id=thread.get('id')).first()
      if not existing_thread:
        model: EmailConversationThread = EmailConversationThread(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect.id,
            subject = thread.get('subject'),
            snippet = thread.get('snippet'),
            prospect_email = prospect.email,
            sdr_email = client_sdr.email,
            nylas_thread_id = thread.get('id'),
            nylas_data = thread
        )
        db.session.add(model)

    db.session.commit()

    return result


def nylas_get_messages(client_sdr_id: int, prospect: Prospect, message_ids: list[str], thread_id: str):

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if message_ids:
      res = requests.get(f'https://api.nylas.com/messages/{",".join(message_ids)}', headers = {"Authorization": f'Bearer {client_sdr.nylas_auth_code}'})
    elif thread_id:
      res = requests.get(f'https://api.nylas.com/messages?thread_id={thread_id}', headers = {"Authorization": f'Bearer {client_sdr.nylas_auth_code}'})
    else:
      return {}

    result = res.json()

    for message in result:
      existing_message = EmailConversationMessage.query.filter_by(nylas_message_id=message.get('id')).first()
      if not existing_message:
        message_from_sdr = False
        message_from = message.get('from')
        if message_from and len(message_from) > 0:
            message_from_email = message_from[0].get('email')
            prospect_email = prospect.email
            if message_from_email != prospect_email:
                message_from_sdr = True

        existing_thread: EmailConversationThread = EmailConversationThread.query.filter_by(nylas_thread_id=message.get('thread_id')).first()
        if not existing_thread:
            raise Exception(f'No thread found for message {message.get("subject")} in SDR: {client_sdr_id}')

        model: EmailConversationMessage = EmailConversationMessage(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect.id,
            subject = message.get('subject'),
            snippet = message.get('snippet'),
            prospect_email = prospect.email,
            sdr_email = client_sdr.email,
            from_sdr = message_from_sdr,
            email_conversation_thread_id=existing_thread.id,
            nylas_thread_id = message.get('thread_id'),
            nylas_message_id = message.get('id'),
            nylas_data = message
        )
        db.session.add(model)

    db.session.commit()

    return result


def prospect_exists_for_client(full_name: str, client_id: int):
    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.filter(
        Prospect.full_name == full_name, Prospect.client_id == client_id
    ).first()

    if p:
        return p
    return None


def get_prospect_generated_message(prospect_id: int, outbound_type: str) -> dict:
    """Gets the generated message for a prospect's outbound type

    Args:
        prospect_id (int): ID of the prospect
        outbound_type (str): Outbound type

    Returns:
        dict: Dictionary of the generated message
    """
    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return {}

    gm: GeneratedMessage = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_type == outbound_type,
        GeneratedMessage.message_status == GeneratedMessageStatus.APPROVED,
    ).first()
    if not gm:
        return {}

    return gm.to_dict()


def create_note(prospect_id: int, note: str):
    note_id = create_prospect_note(prospect_id=prospect_id, note=note)
    return note_id


def update_prospect_status_linkedin(
    prospect_id: int,
    new_status: ProspectStatus,
    message: any = {},
    note: Optional[str] = None,
):
    from src.prospecting.models import Prospect, ProspectStatus, ProspectChannels
    from src.daily_notifications.services import create_engagement_feed_item
    from src.daily_notifications.models import EngagementFeedType

    p: Prospect = Prospect.query.get(prospect_id)
    current_status = p.status

    # Make sure the prospect isn't in the main pipeline for 48 hours
    send_to_purgatory(prospect_id, 2, ProspectHiddenReason.STATUS_CHANGE)

    if note:
        create_note(prospect_id=prospect_id, note=note)

    # notifications
    if new_status == ProspectStatus.ACCEPTED:
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.LINKEDIN.value,
            engagement_type=EngagementFeedType.ACCEPTED_INVITE.value,
            engagement_metadata=message,
        )
        send_status_change_slack_block(
            outreach_type=ProspectChannels.LINKEDIN,
            prospect=p,
            new_status=ProspectStatus.ACCEPTED,
            custom_message=" accepted your invite! 😀",
            metadata=message,
        )
    if new_status == ProspectStatus.ACTIVE_CONVO:
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.LINKEDIN.value,
            engagement_type=EngagementFeedType.ACCEPTED_INVITE.value,
            engagement_metadata=message,
        )
        send_status_change_slack_block(
            outreach_type=ProspectChannels.LINKEDIN,
            prospect=p,
            new_status=ProspectStatus.ACTIVE_CONVO,
            custom_message=" responded to your outreach! 🙌🏽",
            metadata=message,
        )
    if new_status == ProspectStatus.SCHEDULING:
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.LINKEDIN.value,
            engagement_type=EngagementFeedType.SCHEDULING.value,
            engagement_metadata=message,
        )
        send_status_change_slack_block(
            outreach_type=ProspectChannels.LINKEDIN,
            prospect=p,
            new_status=ProspectStatus.SCHEDULING,
            custom_message=" is scheduling! 🙏🔥",
            metadata={"threadUrl": p.li_conversation_thread_id},
        )
    elif new_status == ProspectStatus.DEMO_SET:
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.LINKEDIN.value,
            engagement_type=EngagementFeedType.SET_TIME_TO_DEMO.value,
            engagement_metadata=message,
        )
        send_status_change_slack_block(
            outreach_type=ProspectChannels.LINKEDIN,
            prospect=p,
            new_status=ProspectStatus.DEMO_SET,
            custom_message=" set a time to demo!! 🎉🎉🎉",
            metadata={"threadUrl": p.li_conversation_thread_id},
        )

    # status jumps
    if (
        current_status == ProspectStatus.SENT_OUTREACH
        and new_status == ProspectStatus.RESPONDED
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[ProspectStatus.ACCEPTED, ProspectStatus.RESPONDED],
        )

    if (
        current_status == ProspectStatus.ACCEPTED
        and new_status == ProspectStatus.ACTIVE_CONVO
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
            ],
        )

    if (
        current_status == ProspectStatus.SENT_OUTREACH
        and new_status == ProspectStatus.ACTIVE_CONVO
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACCEPTED,
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
            ],
        )

    if (
        current_status == ProspectStatus.RESPONDED
        and new_status == ProspectStatus.SCHEDULING
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.SCHEDULING,
            ],
        )

    if (
        current_status == ProspectStatus.RESPONDED
        and new_status == ProspectStatus.DEMO_SET
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.SCHEDULING,
                ProspectStatus.DEMO_SET,
            ],
        )

    if (
        current_status == ProspectStatus.ACCEPTED
        and new_status == ProspectStatus.SCHEDULING
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.SCHEDULING,
            ],
        )

    if (
        current_status == ProspectStatus.SENT_OUTREACH
        and new_status == ProspectStatus.SCHEDULING
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACCEPTED,
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.SCHEDULING,
            ],
        )

    if (
        current_status == ProspectStatus.ACTIVE_CONVO
        and new_status == ProspectStatus.DEMO_SET
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.SCHEDULING,
                ProspectStatus.DEMO_SET,
            ],
        )

    if new_status in (
        ProspectStatus.SCHEDULING,
        ProspectStatus.RESPONDED,
        ProspectStatus.NOT_INTERESTED,
    ):
        p.last_reviewed = datetime.now()
        db.session.add(p)
        db.session.commit()

    try:
        update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id, statuses=[new_status]
        )
    except Exception as err:
        return False, err.message if hasattr(err, "message") else err

    return True, "Success"


def update_prospect_status_linkedin_multi_step(prospect_id: int, statuses: list):
    success = True
    for status in statuses:
        success = (
            update_prospect_status_linkedin_helper(
                prospect_id=prospect_id, new_status=status
            )
            and success
        )

    calculate_prospect_overall_status(prospect_id)

    return success, "Success"


def update_prospect_status_linkedin_helper(
    prospect_id: int, new_status: ProspectStatus
):
    # Status Mapping here: https://excalidraw.com/#json=u5Ynh702JjSM1BNnffooZ,OcIRq8s0Ev--ACW10UP4vQ
    from src.prospecting.models import (
        Prospect,
        ProspectStatusRecords,
    )

    p: Prospect = Prospect.query.get(prospect_id)
    if p.status == new_status:
        return True

    if new_status not in VALID_NEXT_LINKEDIN_STATUSES[p.status]:
        raise Exception(f"Invalid status transition from {p.status} to {new_status}")

    record: ProspectStatusRecords = ProspectStatusRecords(
        prospect_id=prospect_id,
        from_status=p.status,
        to_status=new_status,
    )
    db.session.add(record)
    db.session.commit()

    if not p:
        return False

    p.status = new_status

    # Ensures that Active Conversation individuals no longer receive AI responses.
    # Given that the SDR has set this Prospect's Archetype to disable AI after prospect engagement.
    ca: ClientArchetype = ClientArchetype.query.get(p.archetype_id)
    if (
        new_status == ProspectStatus.ACTIVE_CONVO
        and ca.disable_ai_after_prospect_engaged
    ):
        p.deactivate_ai_engagement = True

    db.session.add(p)
    db.session.commit()

    return True


def update_prospect_status_email(
    prospect_id: int,
    new_status: ProspectEmailOutreachStatus,
    override_status: bool = False,
) -> tuple[bool, str]:
    """Updates the prospect email outreach status

    Args:
        prospect_id (int): ID of the prospect (used for the prospect email)
        new_status (ProspectEmailOutreachStatus): New status to update to
        override_status (bool, optional): _description_. Defaults to False.

    Returns:
        tuple[bool, str]: (success, message)
    """
    from src.daily_notifications.services import create_engagement_feed_item
    from src.daily_notifications.models import EngagementFeedType

    # Get the prospect and email record
    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return False, "Prospect not found"
    p_email: ProspectEmail = ProspectEmail.query.filter_by(
        prospect_id=prospect_id
    ).first()
    if not p_email:
        return False, "Prospect email not found"
    p_email_id = p_email.id
    old_status = p_email.outreach_status or ProspectEmailOutreachStatus.UNKNOWN

    # Make sure the prospect isn't in the main pipeline for 48 hours
    send_to_purgatory(prospect_id, 2, ProspectHiddenReason.STATUS_CHANGE)

    # Check if we can override the status, regardless of the current status
    if override_status:
        p_email.outreach_status = new_status
    else:
        # Check if the status is valid to transition to
        if p_email.outreach_status not in VALID_UPDATE_EMAIL_STATUS_MAP[new_status]:
            return (
                False,
                f"Invalid status transition from {p_email.outreach_status} to {new_status}",
            )
        p_email.outreach_status = new_status

    # Send a slack message if the new status is active convo (responded)
    if new_status == ProspectEmailOutreachStatus.ACTIVE_CONVO:
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.EMAIL.value,
            engagement_type=EngagementFeedType.ACCEPTED_INVITE.value,
        )
        send_status_change_slack_block(
            outreach_type=ProspectChannels.EMAIL,
            prospect=p,
            new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
            custom_message=" responded to your email! 🙌🏽",
            metadata={},
        )
    elif new_status == ProspectEmailOutreachStatus.SCHEDULING:  # Scheduling
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.EMAIL.value,
            engagement_type=EngagementFeedType.SCHEDULING.value,
        )
        send_status_change_slack_block(
            outreach_type=ProspectChannels.EMAIL,
            prospect=p,
            new_status=ProspectEmailOutreachStatus.SCHEDULING,
            custom_message=" is scheduling! 🙏🔥",
            metadata={},
        )
    elif new_status == ProspectEmailOutreachStatus.DEMO_SET:  # Demo Set
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.EMAIL.value,
            engagement_type=EngagementFeedType.SET_TIME_TO_DEMO.value,
        )
        send_status_change_slack_block(
            outreach_type=ProspectChannels.EMAIL,
            prospect=p,
            new_status=ProspectEmailOutreachStatus.DEMO_SET,
            custom_message=" set a time to demo!! 🎉🎉🎉",
            metadata={},
        )

    # Commit the changes
    db.session.add(p_email)
    db.session.commit()

    # Add a record to the ProspectEmailStatusRecords table
    record: ProspectEmailStatusRecords = ProspectEmailStatusRecords(
        prospect_email_id=p_email_id,
        from_status=old_status,
        to_status=new_status,
    )
    db.session.add(record)
    db.session.commit()

    # Update the prospect overall status
    calculate_prospect_overall_status(prospect_id=prospect_id)

    return True, "Success"


def send_slack_reminder_for_prospect(prospect_id: int, alert_reason: str):
    """Sends an alert in the Client and Client SDR's Slack channel when a prospect's message needs custom attention.

    Args:
        prospect_id (int): ID of the Prospect
        alert_reason (str): Reason for the alert

    Returns:
        bool: True if the alert was sent successfully, False otherwise
    """
    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return False
    p_name = p.full_name
    last_li_message = p.li_last_message_from_prospect
    li_convo_thread = p.li_conversation_thread_id

    c_csdr_webhook_urls = []
    c: Client = Client.query.get(p.client_id)
    if not c:
        return False
    c_slack_webhook = c.pipeline_notifications_webhook_url
    if c_slack_webhook:
        c_csdr_webhook_urls.append(c_slack_webhook)

    csdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
    if not csdr:
        return False
    csdr_slack_webhook = csdr.pipeline_notifications_webhook_url
    if csdr_slack_webhook:
        c_csdr_webhook_urls.append(csdr_slack_webhook)

    sent = send_slack_message(
        message=f"Prospect {p_name} needs your attention! {alert_reason}",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":rotating_light: {} (#{}) needs your attention".format(
                        p_name, prospect_id
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "{} last responded to you with:\n>{}".format(
                        p_name, last_li_message
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "SellScale AI was uncertain of how to handle the message for the following reason:\n`{}`".format(
                        alert_reason
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Please continue the conversation via LinkedIn",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Go to LinkedIn",
                        "emoji": True,
                    },
                    "value": li_convo_thread or "https://www.linkedin.com",
                    "url": li_convo_thread or "https://www.linkedin.com",
                    "action_id": "button-action",
                },
            },
        ],
        webhook_urls=c_csdr_webhook_urls,
    )
    if sent:
        p.last_reviewed = datetime.now()
        p.deactivate_ai_engagement = True
        db.session.add(p)
        db.session.commit()

    return True


def add_prospect(
    client_id: int,
    archetype_id: int,
    client_sdr_id: int,
    company: Optional[str] = None,
    company_url: Optional[str] = None,
    employee_count: Optional[str] = None,
    full_name: Optional[str] = None,
    industry: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    linkedin_bio: Optional[str] = None,
    linkedin_num_followers: Optional[int] = None,
    title: Optional[str] = None,
    twitter_url: Optional[str] = None,
    email: Optional[str] = None,
    allow_duplicates: bool = True,
) -> int or None:
    """Adds a Prospect to the database.

    Args:
        client_id (int): ID of the Client
        archetype_id (int): ID of the Client Archetype
        client_sdr_id (int): ID of the Client SDR
        company (Optional[str], optional): Name of the Prospect's company. Defaults to None.
        company_url (Optional[str], optional): URL of the Prospect's company. Defaults to None.
        employee_count (Optional[str], optional): Number of employees at the Prospect's company. Defaults to None.
        full_name (Optional[str], optional): Prospect's full name. Defaults to None.
        industry (Optional[str], optional): Prospect's industry. Defaults to None.
        linkedin_url (Optional[str], optional): Prospect's LinkedIn URL. Defaults to None.
        linkedin_bio (Optional[str], optional): Prospect's LinkedIn Bio (Summary). Defaults to None.
        linkedin_num_followers (Optional[int], optional): Number of people who follow the Prospect on LinkedIn. Defaults to None.
        title (Optional[str], optional): Prospect's LinkedIn Title. Defaults to None.
        twitter_url (Optional[str], optional): Prospect's Twitter URL. Defaults to None.
        email (Optional[str], optional): Prospect's email. Defaults to None.
        allow_duplicates (bool, optional): Whether or not to check for duplicate prospects. Defaults to True.

    Returns:
        int or None: ID of the Prospect if it was added successfully, None otherwise
    """
    status = ProspectStatus.PROSPECTED
    overall_status = ProspectOverallStatus.PROSPECTED

    # full_name typically comes fron iScraper LinkedIn, so we run a Title Case check on it
    if full_name and needs_title_casing(full_name):
        full_name = full_name.title()

    # Same thing with company
    if company and needs_title_casing(company):
        company = company.title()

    prospect_exists: Prospect = prospect_exists_for_client(
        full_name=full_name, client_id=client_id
    )
    if (
        prospect_exists and not prospect_exists.email and email
    ):  # If we are adding an email to an existing prospect, this is allowed
        prospect_exists.email = email
        db.session.add(prospect_exists)
        db.session.commit()
        return prospect_exists.id

    if linkedin_url and len(linkedin_url) > 0:
        linkedin_url = linkedin_url.replace("https://www.", "")
        if linkedin_url[-1] == "/":
            linkedin_url = linkedin_url[:-1]

    first_name = get_first_name_from_full_name(full_name=full_name)
    last_name = get_last_name_from_full_name(full_name=full_name)

    can_create_prospect = not prospect_exists or not allow_duplicates
    if can_create_prospect:
        prospect: Prospect = Prospect(
            client_id=client_id,
            archetype_id=archetype_id,
            company=company,
            company_url=company_url,
            employee_count=employee_count,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            industry=industry,
            linkedin_url=linkedin_url,
            linkedin_bio=linkedin_bio,
            title=title,
            twitter_url=twitter_url,
            status=status,
            email=email,
            client_sdr_id=client_sdr_id,
            li_num_followers=linkedin_num_followers,
            overall_status=overall_status,
        )
        db.session.add(prospect)
        db.session.commit()
    else:
        return None

    return prospect.id


def get_linkedin_slug_from_url(url: str):
    try:
        split = url.split("/in/")
        slug_with_suffix = split[1]
        slug_with_suffix = slug_with_suffix.split("?")[0]
        slug = slug_with_suffix.split("/")[0]

        return slug
    except:
        raise Exception("Unable to extract slug.")


def get_navigator_slug_from_url(url: str):
    # https://www.linkedin.com/sales/lead/ACwAAAIwZ58B_JRTBED15c8_ZSr00s5KzlHbt3o,NAME_SEARCH,Y5K9
    # becomes ACwAAAIwZ58B_JRTBED15c8_ZSr00s5KzlHbt3o
    try:
        split = url.split("/lead/")
        slug_with_suffix = split[1]
        slug = slug_with_suffix.split(",")[0]

        return slug
    except:
        raise Exception("Unable to extract slug")


def create_prospects_from_linkedin_link_list(
    url_string: str, archetype_id: int, delimeter: str = "..."
):
    from tqdm import tqdm

    prospect_urls = url_string.split(delimeter)
    batch = generate_random_alphanumeric(32)

    for url in tqdm(prospect_urls):
        create_prospect_from_linkedin_link.delay(
            archetype_id=archetype_id, url=url, batch=batch
        )

    return True


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_linkedin_link(
    self, archetype_id: int, url: str, batch: str = None, email: str = None
):
    try:
        if "/in/" in url:
            slug = get_linkedin_slug_from_url(url)
        elif "/lead/" in url:
            slug = get_navigator_slug_from_url(url)

        payload = research_personal_profile_details(profile_id=slug)

        if payload.get("detail") == "Profile data cannot be retrieved." or not deep_get(
            payload, "first_name"
        ):
            return False

        client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
        client: Client = Client.query.get(client_archetype.client_id)
        client_id = client.id

        company_name = deep_get(payload, "position_groups.0.company.name")
        company_url = deep_get(payload, "position_groups.0.company.url")
        employee_count = (
            str(deep_get(payload, "position_groups.0.company.employees.start"))
            + "-"
            + str(deep_get(payload, "position_groups.0.company.employees.end"))
        )
        full_name = (
            deep_get(payload, "first_name") + " " + deep_get(payload, "last_name")
        )
        industry = deep_get(payload, "industry")
        linkedin_url = "linkedin.com/in/{}".format(deep_get(payload, "profile_id"))
        linkedin_bio = deep_get(payload, "summary")
        title = deep_get(payload, "sub_title")
        twitter_url = None

        # Health Check fields
        followers_count = deep_get(payload, "network_info.followers_count") or 0

        new_prospect_id = add_prospect(
            client_id=client_id,
            archetype_id=archetype_id,
            client_sdr_id=client_archetype.client_sdr_id,
            company=company_name,
            company_url=company_url,
            employee_count=employee_count,
            full_name=full_name,
            industry=industry,
            linkedin_url=linkedin_url,
            linkedin_bio=linkedin_bio,
            title=title,
            twitter_url=twitter_url,
            email=email,
            linkedin_num_followers=followers_count,
        )
        if new_prospect_id is not None:
            create_iscraper_payload_cache(
                linkedin_url=linkedin_url,
                payload=payload,
                payload_type=IScraperPayloadType.PERSONAL,
            )
            return True
        return False
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


def batch_mark_prospects_as_sent_outreach(prospect_ids: list, client_sdr_id: int):
    from src.prospecting.models import Prospect

    updates = []

    for prospect_id in prospect_ids:
        match_prospect_as_sent_outreach.delay(
            prospect_id=prospect_id,
            client_sdr_id=client_sdr_id,
        )

        updates.append(prospect_id)

    return updates


def mark_prospects_as_queued_for_outreach(
    prospect_ids: list, client_sdr_id: int
) -> tuple[bool, dict]:
    """Marks prospects and messages as queued for outreach

    Args:
        prospect_ids (list): List of prospect ids
        client_sdr_id (int): Client SDR id

    Returns:
        bool: True if successful
    """
    from src.campaigns.services import change_campaign_status

    # Get prospects
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids),
        Prospect.client_sdr_id == client_sdr_id,
    ).all()
    prospect_ids = [prospect.id for prospect in prospects]

    # Get messages
    messages: list[GeneratedMessage] = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id.in_(prospect_ids),
        GeneratedMessage.message_status == GeneratedMessageStatus.APPROVED,
    ).all()
    if not messages:
        return False, {
            "error": "No messages in APPROVED found. May have already been queued."
        }
    campaign_id = messages[0].outbound_campaign_id
    messages_ids = [message.id for message in messages]

    # Update prospects
    for id in prospect_ids:
        update_prospect_status_linkedin(id, ProspectStatus.QUEUED_FOR_OUTREACH)

    # Update messages
    updated_messages = []
    for id in messages_ids:
        message: GeneratedMessage = GeneratedMessage.query.get(id)
        message.message_status = GeneratedMessageStatus.QUEUED_FOR_OUTREACH
        message.date_sent = datetime.utcnow()
        updated_messages.append(message)

    # Mark campaign as complete
    if campaign_id is not None:
        change_campaign_status(campaign_id, OutboundCampaignStatus.COMPLETE)

    # Commit
    db.session.bulk_save_objects(updated_messages)
    db.session.commit()

    return True, None


@celery.task(bind=True, max_retries=3)
def match_prospect_as_sent_outreach(self, prospect_id: int, client_sdr_id: int):
    try:
        prospect: Prospect = Prospect.query.get(prospect_id)

        prospect.client_sdr_id = client_sdr_id
        approved_outreach_message_id = prospect.approved_outreach_message_id
        db.session.add(prospect)
        db.session.commit()

        if not prospect or not approved_outreach_message_id:
            return

        update_prospect_status_linkedin(
            prospect_id=prospect_id, new_status=ProspectStatus.SENT_OUTREACH
        )

        message: GeneratedMessage = GeneratedMessage.query.get(
            approved_outreach_message_id
        )
        message.message_status = GeneratedMessageStatus.SENT
        message.date_sent = datetime.now()
        db.session.add(message)

        db.session.commit()
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


def batch_update_prospect_statuses(updates: list):
    for update in updates:
        prospect_id = update.get("id")
        new_status = update.get("status")

        update_prospect_status_linkedin(
            prospect_id=prospect_id, new_status=ProspectStatus[new_status]
        )

    return True


def mark_prospect_reengagement(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.status == ProspectStatus.ACCEPTED:
        update_prospect_status_linkedin(
            prospect_id=prospect_id, new_status=ProspectStatus.RESPONDED
        )

    prospect = Prospect.query.get(prospect_id)
    prospect.last_reviewed = datetime.now()

    if not prospect.times_bumped:
        prospect.times_bumped = 0
    prospect.times_bumped += 1

    db.session.add(prospect)
    db.session.commit()

    return True


def validate_prospect_json_payload(payload: dict, email_enabled: bool = False):
    """Validate the CSV payload sent by the SDR through Retool.
    This is in respect to validating a prospect.

    At the moment, only linkedin_url and email are enforced (one or the other).
    In the future, additional fields can be added as we see fit.

    This is what a sample payload from Retool will look like.
    payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        ....
    ]

    Args:
        payload (dict): The payload sent by the SDR through Retool.

    Returns:
        (bool, str): A tuple of (is_valid, error_message)
    """
    if len(payload) == 0:
        return False, "No prospects were received."

    for prospect in payload:
        email = prospect.get("email")
        linkedin_url = prospect.get("linkedin_url")

        if not linkedin_url:
            return (
                False,
                "Could not find the required 'linkedin_url' field. Please check your CSV, or make sure each Prospect has a linkedin_url field.",
            )

        if email_enabled and not email:
            return (
                False,
                "Since you are uploading an email list, make sure that every row has an email! Please verify your CSV.",
            )

    return True, "No Error"


def add_prospects_from_json_payload(client_id: int, archetype_id: int, payload: dict):
    """
    This is what a sample payload from Retool will look like.
    payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        ....
    ]
    """
    batch_id = generate_random_alphanumeric(32)

    seen_linkedin_urls = set()
    no_duplicates_payload = []
    duplicate_count = 0
    for prospect in payload:
        linkedin_url = prospect.get("linkedin_url")
        if linkedin_url not in seen_linkedin_urls:
            seen_linkedin_urls.add(linkedin_url)
            no_duplicates_payload.append(prospect)
        else:
            duplicate_count += 1

    num_prospects = len(no_duplicates_payload)
    prospect_upload_batch: ProspectUploadBatch = ProspectUploadBatch(
        archetype_id=archetype_id,
        batch_id=batch_id,
        num_prospects=num_prospects,
    )
    db.session.add(prospect_upload_batch)
    db.session.commit()

    for prospect in no_duplicates_payload:
        # These have been validated by the time we get here.
        linkedin_url = prospect.get("linkedin_url")
        email = prospect.get("email")

        create_prospect_from_linkedin_link.delay(
            archetype_id=archetype_id, url=linkedin_url, batch=batch_id, email=email
        )

        # In case the csv has a field, we should stay true to those fields.
        # manual_add_prospect: Prospect = Prospect.query.get(prospect_id)
        # if prospect.get("company"):
        #     manual_add_prospect.company = prospect.get("company")
        # if prospect.get("company_url"):
        #     manual_add_prospect.company_url = prospect.get("company_url")
        # if prospect.get("full_name"):
        #     manual_add_prospect.full_name = prospect.get("full_name")
        # if prospect.get("title"):
        #     manual_add_prospect.title = prospect.get("title")

    return "Success", duplicate_count


def create_prospect_note(prospect_id: int, note: str) -> int:
    """Create a prospect note.

    Args:
        prospect_id (int): ID of the prospect.
        note (str): The note to be added.

    Returns:
        int: ID of the newly created prospect note.
    """
    prospect_note: ProspectNote = ProspectNote(
        prospect_id=prospect_id,
        note=note,
    )
    db.session.add(prospect_note)
    db.session.commit()

    return prospect_note.id


def delete_prospect_by_id(prospect_id: int):
    from src.research.linkedin.services import reset_prospect_research_and_messages

    reset_prospect_research_and_messages(prospect_id=prospect_id)

    prospect: Prospect = Prospect.query.get(prospect_id)
    db.session.delete(prospect)
    db.session.commit()

    return True


def toggle_ai_engagement(prospect_id: int):
    """Toggle AI engagement on/off for a prospect.a"""
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.deactivate_ai_engagement = not prospect.deactivate_ai_engagement
    db.session.add(prospect)
    db.session.commit()

    return True


def batch_mark_as_lead(payload: int):
    """Updates prospects as is_lead

    payload = [
        {'id': 1, 'is_lead': True},
        ...
    ]
    """
    for entry in payload:
        prospect_id = entry["id"]
        is_lead = entry["is_lead"]

        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            continue
        prospect.is_lead = is_lead
        db.session.add(prospect)
        db.session.commit()

    return True


def get_prospect_details(client_sdr_id: int, prospect_id: int) -> dict:
    """Gets prospect details, including linkedin conversation, sdr notes, and company details.

    Args:
        client_sdr_id (int): ID of the Client SDR
        prospect_id (int): ID of the Prospect

    Returns:
        dict: A dictionary containing prospect details, status code, and message.
    """
    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return {"message": "Prospect not found", "status_code": 404}
    if p and p.client_sdr_id != client_sdr_id:
        return {"message": "This prospect does not belong to you", "status_code": 403}
    p_email: ProspectEmail = ProspectEmail.query.filter_by(
        prospect_id=prospect_id
    ).first()
    p_email_status = None
    if p_email and p_email.outreach_status:
        p_email_status = p_email.outreach_status.value

    li_conversation_thread = (
        LinkedinConversationEntry.li_conversation_thread_by_prospect_id(prospect_id)
    )
    li_conversation_thread = [x.to_dict() for x in li_conversation_thread]

    prospect_notes = ProspectNote.get_prospect_notes(prospect_id)
    prospect_notes = [x.to_dict() for x in prospect_notes]

    iset: IScraperExtractorTransformer = IScraperExtractorTransformer(prospect_id)

    company_logo = iset.get_company_logo()
    company_name = iset.get_company_name()
    company_location = iset.get_company_location()
    company_tags = iset.get_company_tags()
    company_tagline = iset.get_company_tagline()
    company_description = iset.get_company_description()
    company_url = iset.get_company_url()
    company_employee_count = iset.get_company_staff_count()

    archetype: ClientArchetype = ClientArchetype.query.get(p.archetype_id)
    archetype_name = archetype.archetype if archetype else None

    return {
        "prospect_info": {
            "details": {
                "id": p.id,
                "full_name": p.full_name,
                "title": p.title,
                "status": p.status.value,
                "overall_status": p.overall_status.value
                if p.overall_status
                else p.status.value,
                "linkedin_status": p.status.value,
                "email_status": p_email_status,
                "profile_pic": p.img_url,
                "ai_responses_disabled": p.deactivate_ai_engagement,
                "notes": prospect_notes,
                "persona": archetype_name,
            },
            "li": {
                "li_conversation_url": p.li_conversation_thread_id,
                "li_conversation_thread": li_conversation_thread,
                "li_profile": p.linkedin_url,
            },
            "email": {"email": p.email, "email_status": ""},
            "company": {
                "logo": company_logo,
                "name": company_name,
                "location": company_location,
                "tags": company_tags,
                "tagline": company_tagline,
                "description": company_description,
                "url": company_url,
                "employee_count": company_employee_count,
            },
        },
        "status_code": 200,
        "message": "Success",
    }


def map_prospect_linkedin_status_to_prospect_overall_status(
    prospect_linkedin_status: ProspectStatus,
):
    prospect_status_map = {
        ProspectStatus.PROSPECTED: ProspectOverallStatus.PROSPECTED,
        ProspectStatus.QUEUED_FOR_OUTREACH: ProspectOverallStatus.PROSPECTED,
        ProspectStatus.SEND_OUTREACH_FAILED: ProspectOverallStatus.REMOVED,
        ProspectStatus.NOT_QUALIFIED: ProspectOverallStatus.REMOVED,
        ProspectStatus.SENT_OUTREACH: ProspectOverallStatus.SENT_OUTREACH,
        ProspectStatus.ACCEPTED: ProspectOverallStatus.ACCEPTED,
        ProspectStatus.RESPONDED: ProspectOverallStatus.BUMPED,
        ProspectStatus.ACTIVE_CONVO: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_INTERESTED: ProspectOverallStatus.REMOVED,
        ProspectStatus.DEMO_SET: ProspectOverallStatus.DEMO,
        ProspectStatus.DEMO_WON: ProspectOverallStatus.DEMO,
        ProspectStatus.DEMO_LOSS: ProspectOverallStatus.DEMO,
    }
    if prospect_linkedin_status in prospect_status_map:
        return prospect_status_map[prospect_linkedin_status]
    return None


def map_prospect_email_status_to_prospect_overall_status(
    prospect_email_status: ProspectEmailOutreachStatus,
):
    prospect_email_status_map = {
        ProspectEmailOutreachStatus.UNKNOWN: ProspectOverallStatus.PROSPECTED,
        ProspectEmailOutreachStatus.NOT_SENT: ProspectOverallStatus.PROSPECTED,
        ProspectEmailOutreachStatus.SENT_OUTREACH: ProspectOverallStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.EMAIL_OPENED: ProspectOverallStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACCEPTED: ProspectOverallStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.SCHEDULING: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.DEMO_SET: ProspectOverallStatus.DEMO,
        ProspectEmailOutreachStatus.DEMO_WON: ProspectOverallStatus.DEMO,
        ProspectEmailOutreachStatus.DEMO_LOST: ProspectOverallStatus.DEMO,
    }
    if prospect_email_status in prospect_email_status_map:
        return prospect_email_status_map[prospect_email_status]
    return None


@celery.task
def calculate_prospect_overall_status(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None

    prospect_email_overall_status: ProspectOverallStatus | None = None
    prospect_email: ProspectEmail = ProspectEmail.query.filter_by(
        prospect_id=prospect_id
    ).first()
    if prospect_email:
        prospect_email_status: ProspectEmailOutreachStatus = (
            prospect_email.outreach_status
        )
        prospect_email_overall_status: ProspectOverallStatus | None = (
            map_prospect_email_status_to_prospect_overall_status(prospect_email_status)
        )

    prospect_li_status: ProspectStatus = prospect.status
    prospect_li_overall_status: ProspectOverallStatus | None = (
        map_prospect_linkedin_status_to_prospect_overall_status(prospect_li_status)
    )

    all_channel_statuses = [
        prospect_email_overall_status,
        prospect_li_overall_status,
    ]
    all_channel_statuses = [x for x in all_channel_statuses if x is not None]

    # get max status based on .get_rank()
    if all_channel_statuses:
        max_status = max(all_channel_statuses, key=lambda x: x.get_rank())
        prospect = Prospect.query.get(prospect_id)
        prospect.overall_status = max_status
        db.session.add(prospect)
        db.session.commit()

    return None


def get_valid_channel_type_choices(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return []
    valid_channel_types = []
    if prospect.approved_outreach_message_id:
        valid_channel_types.append({"label": "Linkedin", "value": "LINKEDIN"})
    if prospect.approved_prospect_email_id:
        valid_channel_types.append({"label": "Email", "value": "EMAIL"})
    return valid_channel_types


def update_all_last_reviewed_and_times_bumped():
    """
    Updates the last reviewed and times bumped fields for all prospects with a
    linkedin conversation thread.
    """
    query = """
        with d as (
            select
                prospect.id,
                prospect.last_reviewed,
                prospect.times_bumped,
                prospect.li_conversation_thread_id,
                max(linkedin_conversation_entry.date) latest_conversation_entry,
                count(linkedin_conversation_entry.id) filter (where linkedin_conversation_entry.connection_degree = 'You') num_messages_from_sdr
            from prospect
                left join linkedin_conversation_entry on linkedin_conversation_entry.conversation_url = prospect.li_conversation_thread_id
            where prospect.li_conversation_thread_id is not null
            group by 1,2,3,4
        )
        select
            id,
            case when latest_conversation_entry > last_reviewed then latest_conversation_entry
            	else last_reviewed end new_last_reviewed,
            case when times_bumped > num_messages_from_sdr then times_bumped
                else num_messages_from_sdr end new_times_bumped
        from d;
    """
    data = db.session.execute(query).fetchall()
    for row in data:
        update_last_reviewed_and_times_bumped.delay(
            prospect_id=row[0],
            new_last_reviewed=row[1],
            new_times_bumped=row[2],
        )


@celery.task
def update_last_reviewed_and_times_bumped(
    prospect_id, new_last_reviewed, new_times_bumped
):
    prospect = Prospect.query.get(prospect_id)
    prospect.last_reviewed = new_last_reviewed
    prospect.times_bumped = new_times_bumped
    db.session.add(prospect)
    db.session.commit()


def mark_prospect_as_removed(client_sdr_id: int, prospect_id: int) -> bool:
    """
    Removes a prospect from being contacted if their client_sdr assigned
    is the same as the client_sdr calling this.
    """
    prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return False

    prospect.overall_status = ProspectOverallStatus.REMOVED
    db.session.add(prospect)
    db.session.commit()
    return True


def send_to_purgatory(prospect_id: int, days: int, reason: ProspectHiddenReason):
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.hidden_until = datetime.datetime.utcnow() + datetime.timedelta(days=days)
    prospect.hidden_reason = reason
    db.session.add(prospect)
    db.session.commit()
