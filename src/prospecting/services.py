from datetime import datetime
from typing import List, Optional, Union
from sqlalchemy import nullslast
from src.email_outbound.email_store.hunter import find_hunter_email_from_prospect_id
from src.email_outbound.email_store.services import create_email_store, email_store_hunter_verify

from src.individual.services import add_individual_from_prospect
from src.campaigns.models import OutboundCampaign

from src.company.services import find_company_for_prospect
from src.email_outbound.models import EmailConversationThread, EmailConversationMessage
from sqlalchemy import or_
import requests
from src.message_generation.models import (
    GeneratedMessage,
    GeneratedMessageStatus,
    GeneratedMessageType,
)
from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailStatus,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords,
    VALID_UPDATE_EMAIL_STATUS_MAP,
)
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.icp_score.services import apply_icp_scoring_ruleset_filters_task
from src.research.linkedin.services import (
    get_research_and_bullet_points_new,
    get_research_payload_new,
)
from src.research.services import create_iscraper_payload_cache
from src.prospecting.models import (
    Prospect,
    ProspectChannels,
    ProspectStatus,
    ProspectStatusRecords,
    ProspectUploadBatch,
    ProspectNote,
    ProspectOverallStatus,
    ProspectHiddenReason,
    ProspectReferral,
    ProspectMessageFeedback,
    VALID_NEXT_LINKEDIN_STATUSES,
)
from app import db, celery
from src.utils.abstract.attr_utils import deep_get
from src.utils.random_string import generate_random_alphanumeric
from src.utils.slack import (
    URL_MAP,
    CHANNEL_NAME_MAP,
    send_slack_message,
    send_delayed_slack_message,
)
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
from datetime import timedelta
from flask import jsonify


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
    persona_id: int = None,
    limit: int = 50,
    offset: int = 0,
    ordering: list[dict[str, int]] = [],
    bumped: str = "all",
    show_purgatory: Union[bool, str] = False,
    prospect_id: int = None,
    icp_fit_score: int = None,
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
        bumped (str, optional): Filter by bumped status. Defaults to 'all'.
        show_purgatory (bool, optional): Whether to show purgatory prospects. Defaults to False.
        prospect_id (int, optional): Filter by prospect ID. Defaults to None.
        icp_fit_score (int, optional): Filter by ICP fit score. Defaults to None.

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
                ordering_arr.append(nullslast(Prospect.icp_fit_score.asc()))
            elif order_direction == -1:
                ordering_arr.append(nullslast(Prospect.icp_fit_score.desc()))

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
            ProspectEmail,
            Prospect.approved_prospect_email_id == ProspectEmail.id,
            isouter=True,
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
    if persona_id:
        prospects = prospects.filter(Prospect.archetype_id == persona_id)
    if bumped != "all":
        prospects = prospects.filter(Prospect.times_bumped == int(bumped))
    if prospect_id:
        prospects = prospects.filter(Prospect.id == prospect_id)
    if icp_fit_score:
        prospects = prospects.filter(Prospect.icp_fit_score == icp_fit_score)

    # if show_purgatory != "ALL":
    #     if not show_purgatory:
    #         prospects = prospects.filter(
    #             or_(
    #                 Prospect.hidden_until == None,
    #                 Prospect.hidden_until < datetime.datetime.utcnow(),
    #             )
    #         )
    #     else:
    #         prospects = prospects.filter(
    #             Prospect.hidden_until >= datetime.datetime.utcnow()
    #         )

    total_count = prospects.count()
    prospects = prospects.limit(limit).offset(offset).all()

    return {"total_count": total_count, "prospects": prospects}


def get_prospects_for_icp_table(
    client_sdr_id: int,
    client_archetype_id: int,
    get_sample: Optional[bool] = False,
) -> list[dict]:
    """Gets prospects belonging to the SDR, focusing on the ICP

    Args:
        client_sdr_id (int): ID of the SDR, supplied by the require_user decorator
        client_archetype_id (int): ID of the Client Archetype

    Returns:
        list[Prospect]: List of prospects
    """
    result = db.session.execute(
        '''
            select
                prospect.full_name,
                prospect.title,
                prospect.company,
                prospect.linkedin_url,
                prospect.icp_fit_score,
                prospect.icp_fit_reason,
                prospect.industry,
                prospect.id
            from prospect
                join client_sdr on client_sdr.id = prospect.client_sdr_id
            where prospect.archetype_id = {client_archetype_id}
                and client_sdr.id = {client_sdr_id}
                and prospect.overall_status <> 'REMOVED'
            order by 1 asc
        '''.format(
                client_archetype_id=client_archetype_id,
                client_sdr_id=client_sdr_id,
        )
    ).fetchall()

    prospects = []
    if get_sample:
        result = result[:50]

    for r in result:
        prospects.append({
            "full_name": r[0],
            "title": r[1],
            "company": r[2],
            "linkedin_url": r[3],
            "icp_fit_score": r[4],
            "icp_fit_reason": r[5],
            "industry": r[6],
            "id": r[7],
        })

    return prospects


def patch_prospect(
    prospect_id: int,
    title: Optional[str] = None,
    email: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    company_name: Optional[str] = None,
    company_website: Optional[str] = None,
    contract_size: Optional[int] = None,
) -> bool:
    """Modifies fields of a prospect

    Args:
        prospect_id (int): ID of the prospect to modify
        title (Optional[str], optional): The prospect's title (role). Defaults to None.
        email (Optional[str], optional): The prospect's email. Defaults to None.
        linkedin_url (Optional[str], optional): The prospect's LinkedIn URL. Defaults to None.
        company_name (Optional[str], optional): The prospect's current company name. Defaults to None.
        company_website (Optional[str], optional): The website of the prospect's current company. Defaults to None.
        contract_size (Optional[int], optional): The prospect's contract size. Defaults to None.

    Returns:
        bool: True if the prospect was modified, False otherwise
    """

    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return False

    if title:
        p.title = title
    if linkedin_url:
        p.linkedin_url = linkedin_url
    if contract_size:
        p.contract_size = contract_size
    db.session.commit()

    # If email is changed, we add to email store and try to verify
    if email:
        p.email = email
        email_store_id = create_email_store(
            email=email,
            first_name=p.first_name,
            last_name=p.last_name,
            company_name=p.company,
        )
        if email_store_id:
            p.email_store_id = email_store_id
            email_store_hunter_verify.delay(email_store_id=email_store_id)

    # If the company has changed, we try to find the company
    if company_name:
        p.company = company_name
        find_company_for_prospect(p.id)
    if company_website:
        p.company_url = company_website
        find_company_for_prospect(p.id)

    db.session.commit()
    return True


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
    manually_send_to_purgatory: bool = False,
    quietly: Optional[bool] = False,
    override_status: Optional[bool] = False,
) -> tuple[bool, str]:
    from src.prospecting.models import Prospect, ProspectStatus, ProspectChannels
    from src.daily_notifications.services import create_engagement_feed_item
    from src.daily_notifications.models import EngagementFeedType

    p: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
    current_status = p.status

    # If the new status isn't an active convo sub status, does not start with ACTIVE_CONVO
    if manually_send_to_purgatory and "ACTIVE_CONVO_" not in new_status.value:
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
    if (
        new_status == ProspectStatus.ACTIVE_CONVO
        and "ACTIVE_CONVO" not in current_status.value
    ):
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
            custom_message=" responded to your LinkedIn Invite! 🙌",
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
        if not quietly:
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
    elif new_status == ProspectStatus.ACTIVE_CONVO_SCHEDULING:
        create_engagement_feed_item(
            client_sdr_id=p.client_sdr_id,
            prospect_id=p.id,
            channel_type=ProspectChannels.LINKEDIN.value,
            engagement_type=EngagementFeedType.SCHEDULING.value,
            engagement_metadata=message,
        )
        if not quietly:
            send_status_change_slack_block(
                outreach_type=ProspectChannels.LINKEDIN,
                prospect=p,
                new_status=ProspectStatus.ACTIVE_CONVO_SCHEDULING,
                custom_message=" is scheduling! 🙏🔥",
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
            override_status=override_status,
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
            override_status=override_status,
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
            override_status=override_status,
        )

    if (
        current_status == ProspectStatus.RESPONDED
        and new_status == ProspectStatus.DEMO_SET
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.DEMO_SET,
            ],
            override_status=override_status,
        )

    if (
        current_status == ProspectStatus.ACTIVE_CONVO
        and new_status == ProspectStatus.DEMO_SET
    ):
        return update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.DEMO_SET,
            ],
            override_status=override_status,
        )

    if new_status in (
        ProspectStatus.SCHEDULING,
        ProspectStatus.RESPONDED,
        ProspectStatus.NOT_INTERESTED,
    ):
        db.session.add(p)
        db.session.commit()

    try:
        update_prospect_status_linkedin_multi_step(
            prospect_id=prospect_id,
            statuses=[new_status],
            override_status=override_status,
        )
    except Exception as err:
        return False, err.message if hasattr(err, "message") else err

    # Update the prospect overall status
    calculate_prospect_overall_status(prospect_id=prospect_id)

    return True, "Success"


def update_prospect_status_linkedin_multi_step(
    prospect_id: int, statuses: list, override_status: bool = False
):
    success = True
    for status in statuses:
        success = (
            update_prospect_status_linkedin_helper(
                prospect_id=prospect_id,
                new_status=status,
                override_status=override_status,
            )
            and success
        )

    calculate_prospect_overall_status(prospect_id)

    return success, "Success"


def update_prospect_status_linkedin_helper(
    prospect_id: int, new_status: ProspectStatus, override_status: bool = False
):
    # Status Mapping here: https://excalidraw.com/#json=u5Ynh702JjSM1BNnffooZ,OcIRq8s0Ev--ACW10UP4vQ
    from src.prospecting.models import (
        Prospect,
        ProspectStatusRecords,
    )

    p: Prospect = Prospect.query.get(prospect_id)
    if p.status == new_status:
        return True

    if not override_status and new_status not in VALID_NEXT_LINKEDIN_STATUSES[p.status]:
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

    db.session.add(p)
    db.session.commit()

    if new_status == ProspectStatus.ACTIVE_CONVO:
        find_hunter_email_from_prospect_id.delay(
            prospect_id=prospect_id, trigger_from="status change"
        )

    return True


def update_prospect_status_email(
    prospect_id: int,
    new_status: ProspectEmailOutreachStatus,
    override_status: bool = False,
    manually_send_to_purgatory: bool = False,
    quietly: Optional[bool] = False,
) -> tuple[bool, str]:
    """Updates the prospect email outreach status

    Args:
        prospect_id (int): ID of the prospect (used for the prospect email)
        new_status (ProspectEmailOutreachStatus): New status to update to
        override_status (bool, optional): _description_. Defaults to False.
        quietly (Optional[bool], optional): Don't send slack notifs. Defaults to False.

    Returns:
        tuple[bool, str]: (success, message)
    """
    from src.daily_notifications.services import create_engagement_feed_item
    from src.daily_notifications.models import EngagementFeedType

    # Get the prospect and email record
    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return False, "Prospect not found"
    p_email: ProspectEmail = ProspectEmail.query.get(p.approved_prospect_email_id)
    if not p_email:
        return False, "Prospect email not found"
    p_email_id = p_email.id
    old_status = p_email.outreach_status or ProspectEmailOutreachStatus.UNKNOWN

    if manually_send_to_purgatory:
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
    synchronous_research: bool = False,
    set_status: ProspectStatus = ProspectStatus.PROSPECTED,
    set_note: str = None,
    is_lookalike_profile: bool = False,
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
        synchronous_research (bool, optional): Whether or not to run synchronous research on the Prospect. Defaults to False.
        set_status (ProspectStatus, optional): Status to set the Prospect to. Defaults to ProspectStatus.PROSPECTED.
        set_note (str, optional): Note to add to the Prospect. Defaults to None.

    Returns:
        int or None: ID of the Prospect if it was added successfully, None otherwise
    """
    status = set_status
    overall_status = map_prospect_linkedin_status_to_prospect_overall_status(status)

    # full_name typically comes fron iScraper LinkedIn, so we run a Title Case check on it
    if full_name and needs_title_casing(full_name):
        full_name = full_name.title()

    # Same thing with company
    if company and needs_title_casing(company):
        company = company.title()

    # Check for duplicates
    prospect_exists: Prospect = prospect_exists_for_client(
        full_name=full_name, client_id=client_id
    )
    prospect_persona: ClientArchetype = None
    if prospect_exists:
        prospect_persona = ClientArchetype.query.filter_by(
            id=prospect_exists.archetype_id
        ).first()
        if (
            prospect_exists.archetype_id != archetype_id
            and prospect_persona.is_unassigned_contact_archetype
        ):
            prospect_exists.archetype_id = archetype_id
            db.session.add(prospect_exists)
            db.session.commit()
            return prospect_exists.id
        if (
            not prospect_exists.email and email
        ):  # If we are adding an email to an existing prospect, this is allowed
            prospect_exists.email = email
            db.session.add(prospect_exists)
            db.session.commit()
            return prospect_exists.id

        # No good reason to have duplicate. Return None
        return None

    if linkedin_url and len(linkedin_url) > 0:
        linkedin_url = linkedin_url.replace("https://www.", "")
        if linkedin_url[-1] == "/":
            linkedin_url = linkedin_url[:-1]

    first_name = get_first_name_from_full_name(full_name=full_name)
    last_name = get_last_name_from_full_name(full_name=full_name)

    client: Client = Client.query.get(client_id)
    if company:
        if (
            client.do_not_contact_company_names
            and company.lower()
            in [x.lower() for x in client.do_not_contact_company_names]
        ) or (
            client.do_not_contact_keywords_in_company_names
            and company.lower()
            in [x.lower() for x in client.do_not_contact_keywords_in_company_names]
        ):
            status = ProspectStatus.NOT_QUALIFIED
            overall_status = ProspectOverallStatus.REMOVED

    can_create_prospect = not prospect_exists or not allow_duplicates
    if can_create_prospect:

        archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
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
            active=True,
            contract_size=archetype.contract_size,
            is_lookalike_profile=is_lookalike_profile,
        )
        db.session.add(prospect)
        db.session.commit()
        p_id = prospect.id
        prospect: Prospect = Prospect.query.get(p_id)
        prospect.regenerate_uuid()

        # Get research and bullet points for the prospect (synchronous OR asynchronous)
        if synchronous_research:
            get_research_and_bullet_points_new(prospect_id=p_id, test_mode=False)
        else:
            get_research_and_bullet_points_new.delay(prospect_id=p_id, test_mode=False)
    else:
        return None

    # Verify the email if it exists
    if email:
        email_store_id = create_email_store(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company_name=company
        )
        if email_store_id:
            email_store_hunter_verify.delay(email_store_id=email_store_id)

    # Get research payload
    get_research_payload_new(prospect_id=p_id, test_mode=False)

    # Find the company details for the prospect
    find_company_for_prospect(p_id)

    # Store the prospect as an Individual
    add_individual_from_prospect(p_id)

    if set_note:
        create_prospect_note(prospect_id=p_id, note=set_note)

    # Apply ICP Scoring Ruleset filters
    apply_icp_scoring_ruleset_filters_task(
        client_archetype_id=archetype_id, prospect_ids=[p_id]
    )

    return p_id


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
    url_string: str,
    archetype_id: int,
    delimeter: str = "...",
    set_status: ProspectStatus = ProspectStatus.PROSPECTED,
    set_note: str = None,
):
    from tqdm import tqdm

    prospect_urls = url_string.split(delimeter)
    batch = generate_random_alphanumeric(32)

    for url in tqdm(prospect_urls):
        create_prospect_from_linkedin_link.delay(
            archetype_id=archetype_id,
            url=url,
            batch=batch,
            set_status=set_status,
            set_note=set_note,
        )

    return True


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_linkedin_link(
    self,
    archetype_id: int,
    url: str,
    batch: str = None,
    email: str = None,
    synchronous_research: bool = False,
    allow_duplicates: bool = True,
    set_status: ProspectStatus = ProspectStatus.PROSPECTED,
    set_note: str = None,
    is_lookalike_profile: bool = False,
) -> tuple[bool, int or str]:
    from src.research.linkedin.services import research_personal_profile_details

    try:
        if "/in/" in url:
            slug = get_linkedin_slug_from_url(url)
        elif "/lead/" in url:
            slug = get_navigator_slug_from_url(url)

        payload = research_personal_profile_details(profile_id=slug)

        if payload.get("detail") == "Profile data cannot be retrieved." or not deep_get(
            payload, "first_name"
        ):
            return False, "Profile data cannot be retrieved."

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
            synchronous_research=synchronous_research,
            allow_duplicates=allow_duplicates,
            set_status=set_status,
            set_note=set_note,
            is_lookalike_profile=is_lookalike_profile,
        )
        if new_prospect_id is not None:
            create_iscraper_payload_cache(
                linkedin_url=linkedin_url,
                payload=payload,
                payload_type=IScraperPayloadType.PERSONAL,
            )
            return True, new_prospect_id
        return False, "Prospect already exists"
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

    db.session.commit()

    # Update messages
    updated_messages = []
    for id in messages_ids:
        message: GeneratedMessage = GeneratedMessage.query.get(id)
        message.message_status = GeneratedMessageStatus.QUEUED_FOR_OUTREACH
        message.date_sent = datetime.datetime.utcnow()
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

    if not prospect.times_bumped:
        prospect.times_bumped = 0
    prospect.times_bumped += 1

    db.session.add(prospect)
    db.session.commit()

    return True


def validate_prospect_json_payload(payload: dict):
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

        if not linkedin_url and not email:
            return (
                False,
                "Could not find the required 'linkedin_url' or 'email' field. Please check your CSV, or make sure each Prospect has a linkedin_url or email field.",
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


def toggle_ai_engagement(client_sdr_id: int, prospect_id: int):
    """Toggle AI engagement on/off for a prospect.a"""
    prospect: Prospect = Prospect.query.filter_by(
        client_sdr_id=client_sdr_id, id=prospect_id
    ).first()
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
    p_email: ProspectEmail = ProspectEmail.query.get(p.approved_prospect_email_id)
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

    # Get referrals
    referrals = db.session.execute(
        f"""
            SELECT p_2.id, p_2.full_name
            FROM prospect as p_1
            JOIN prospect_referral ON p_1.id = prospect_referral.referral_id
            JOIN prospect as p_2 ON prospect_referral.referred_id = p_2.id
            where p_1.id = {p.id};
          """
    ).fetchall()
    referrals = [dict(row) for row in referrals]

    # Get referred
    referred = db.session.execute(
        f"""
            SELECT p_1.id, p_1.full_name
            FROM prospect as p_1
            JOIN prospect_referral ON p_1.id = prospect_referral.referral_id
            JOIN prospect as p_2 ON prospect_referral.referred_id = p_2.id
            where p_2.id = {p.id};
          """
    ).fetchall()
    referred = [dict(row) for row in referred]

    return {
        "prospect_info": {
            "details": {
                "id": p.id,
                "full_name": p.full_name,
                "title": p.title,
                "company": p.company,
                "address": "",
                "status": p.status.value,
                "overall_status": p.overall_status.value
                if p.overall_status
                else p.status.value,
                "linkedin_status": p.status.value,
                "bump_count": p.times_bumped,
                "icp_fit_score": p.icp_fit_score,
                "icp_fit_reason": p.icp_fit_reason,
                "email_status": p_email_status,
                "profile_pic": p.img_url,
                "ai_responses_disabled": p.deactivate_ai_engagement,
                "notes": prospect_notes,
                "persona": archetype_name,
                "persona_id": p.archetype_id,
                "demo_date": p.demo_date,
            },
            "data": p.to_dict(),
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
            "referrals": referrals,
            "referred": referred,
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
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_OBJECTION: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_QUESTION: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_REVIVAL: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_INTERESTED: ProspectOverallStatus.NURTURE,
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
        ProspectEmailOutreachStatus.BOUNCED: ProspectOverallStatus.REMOVED,
        ProspectEmailOutreachStatus.SENT_OUTREACH: ProspectOverallStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.EMAIL_OPENED: ProspectOverallStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACCEPTED: ProspectOverallStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.SCHEDULING: ProspectOverallStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.UNSUBSCRIBED: ProspectOverallStatus.REMOVED,
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

    if prospect.approved_prospect_email_id:
        prospect_email: Optional[ProspectEmail] = ProspectEmail.query.get(
            prospect.approved_prospect_email_id
        )
    else:
        prospect_email = None

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
        update_last_reviewed_and_times_bumped(
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
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return False

    # Create a record
    prospect_removed = ProspectStatusRecords(
        prospect_id=prospect_id,
        from_status=prospect.status,
        to_status=ProspectStatus.NOT_QUALIFIED,
    )
    db.session.add(prospect_removed)

    # Remove the prospect
    prospect.overall_status = ProspectOverallStatus.REMOVED
    prospect.status = ProspectStatus.NOT_QUALIFIED

    # If the prospect has linkedin generated message mark them as blocked
    # Only mark as blocked if the message has not been sent (it's too late otherwise)
    if prospect.approved_outreach_message_id:
        message: GeneratedMessage = GeneratedMessage.query.get(
            prospect.approved_outreach_message_id
        )
        if message.message_status != GeneratedMessageStatus.SENT:
            message.message_status = GeneratedMessageStatus.BLOCKED

    # Do the same for messages sent via email
    if prospect.approved_prospect_email_id:
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect.approved_prospect_email_id
        )
        if prospect_email.personalized_first_line:
            first_line: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_first_line
            )
            if first_line.message_status != GeneratedMessageStatus.SENT:
                first_line.message_status = GeneratedMessageStatus.BLOCKED
        if prospect_email.personalized_subject_line:
            subject_line: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_subject_line
            )
            if subject_line.message_status != GeneratedMessageStatus.SENT:
                subject_line.message_status = GeneratedMessageStatus.BLOCKED
        if prospect_email.personalized_body:
            body: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_body
            )
            if body.message_status != GeneratedMessageStatus.SENT:
                body.message_status = GeneratedMessageStatus.BLOCKED

    db.session.add(prospect)
    db.session.commit()
    return True


def send_to_purgatory(prospect_id: int, days: int, reason: ProspectHiddenReason):
    prospect: Prospect = Prospect.query.get(prospect_id)
    new_hidden_until = datetime.datetime.utcnow() + datetime.timedelta(days=days)

    if (
        prospect.overall_status == ProspectOverallStatus.ACCEPTED
        or prospect.overall_status == ProspectOverallStatus.PROSPECTED
        or prospect.overall_status == ProspectOverallStatus.SENT_OUTREACH
    ):
        return

    if prospect.hidden_until is None or new_hidden_until > prospect.hidden_until:
        prospect.hidden_until = new_hidden_until
        prospect.hidden_reason = reason
        db.session.add(prospect)
        db.session.commit()


def update_prospect_demo_date(
    client_sdr_id: int, prospect_id: int, demo_date: str, send_reminder: bool = False
):
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.demo_date = demo_date
    db.session.add(prospect)
    db.session.commit()

    date = datetime.datetime.fromisoformat(demo_date[:-1])
    if send_reminder:

        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        send_delayed_slack_message(
            message=f"""
              Demo reminder requested for prospect below:
              SDR Name: {sdr.name}
              Prospect name: {prospect.full_name}
              Demo date: {date.strftime("%m/%d/%Y")}
              Please send a reminder to engage with prospect and confirm they'll be meeting.
            """,
            channel_name=CHANNEL_NAME_MAP["prospect-demo-soon"],
            delay_date=(date - timedelta(days=2)),
        )

    return True


@celery.task
def auto_mark_uninterested_bumped_prospects():
    prospects = db.session.execute(
        """
        select
            prospect.id,
            prospect.full_name,
            client_sdr.name,
            count(*)
        from prospect
            join linkedin_conversation_entry on linkedin_conversation_entry.thread_urn_id = prospect.li_conversation_urn_id
            join client_sdr on client_sdr.id = prospect.client_sdr_id
        where prospect.overall_status = 'BUMPED'
        group by 1,2,3
        having count(*) > 3;
    """
    )
    for prospect in prospects:
        prospect_id = prospect[0]
        prospect_name = prospect[1]
        client_sdr_name = prospect[2]
        prospect_count = prospect[3]
        message = f"⚠️ {prospect_name} has been bumped {prospect_count - 1} times by {client_sdr_name} and is now being marked as `nurturing mode`."
        send_slack_message(message=message, webhook_urls=[URL_MAP["csm-convo-sorter"]])

        update_prospect_status_linkedin(
            prospect_id=prospect_id,
            new_status=ProspectStatus.NOT_INTERESTED,
            note=f"Auto-marked as `not interested` after being bumped {prospect_count - 1} times.",
        )


def find_prospect_id_from_li_or_email(
    client_sdr_id: int, li_url: Optional[str], email: Optional[str]
) -> Optional[int]:
    if li_url:
        li_public_id = li_url.split("/in/")[1].split("/")[0]
        prospect = Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            or_(
                Prospect.linkedin_url.ilike(f"%/in/{li_public_id}"),
                Prospect.linkedin_url.ilike(f"%/in/{li_public_id}/%"),
            ),
        ).first()
        if prospect:
            return prospect.id

    if email:
        prospect = Prospect.query.filter_by(email=email).first()
        if prospect:
            return prospect.id

    return None


def get_prospect_li_history(prospect_id: int):

    from model_import import ProspectStatusRecords, DemoFeedback, GeneratedMessageStatus

    prospect: Prospect = Prospect.query.get(prospect_id)
    intro_msg: GeneratedMessage = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_status == GeneratedMessageStatus.SENT,
    ).first()
    prospect_notes: List[ProspectNote] = ProspectNote.get_prospect_notes(prospect_id)
    convo_history: List[
        LinkedinConversationEntry
    ] = LinkedinConversationEntry.li_conversation_thread_by_prospect_id(prospect_id)
    status_history: List[ProspectStatusRecords] = ProspectStatusRecords.query.filter(
        ProspectStatusRecords.prospect_id == prospect_id
    ).all()
    demo_feedback: DemoFeedback = DemoFeedback.query.filter(
        DemoFeedback.prospect_id == prospect_id,
    ).first()

    return {
        "creation_date": prospect.created_at,
        "intro_msg": {
            "message": intro_msg.completion,
            "date": intro_msg.date_sent,
        }
        if intro_msg
        else None,
        "notes": [{"message": n.note, "date": n.created_at} for n in prospect_notes],
        "convo": [
            {"author": c.connection_degree, "message": c.message, "date": c.date}
            for c in convo_history
        ],
        "statuses": [
            {"from": s.from_status.value, "to": s.to_status.value, "date": s.created_at}
            for s in status_history
        ],
        "demo_feedback": {
            "status": demo_feedback.status,
            "rating": demo_feedback.rating,
            "feedback": demo_feedback.feedback,
            "date": demo_feedback.created_at,
        }
        if demo_feedback
        else None,
    }


def send_li_outreach_connection(
    prospect_id: int,
    message: str,
    campaign_id: Optional[int] = None,
    config_id: Optional[int] = None,
) -> int:
    """Sends a LinkedIn outreach connection message to a prospect. This is very async, it will happen eventually
    based on our PhantomBuster schedule.

    Args:
        prospect_id: The ID of the Prospect to send the message to.
        message: The message to send to the Prospect.
        campaign_id: The ID of the outbound_campaign that this message is part of.
        config_id: The ID of the stack_ranked_message_generation_configuration_id that this message is part of.

    Returns:
        The ID of the GeneratedMessage that was created.
    """
    # Create a new GeneratedMessage
    outreach_msg = GeneratedMessage(
        prospect_id=prospect_id,
        research_points=[],
        prompt="",
        completion=message,
        message_status=GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
        message_type=GeneratedMessageType.LINKEDIN,
        stack_ranked_message_generation_configuration_id=config_id,
        outbound_campaign_id=campaign_id,
        few_shot_prompt="",
        priority_rating=10,
        ai_approved=True,
    )
    db.session.add(outreach_msg)
    db.session.commit()
    generated_message_id = outreach_msg.id

    # Attach the GeneratedMessage to the Prospect
    prospect_referred: Prospect = Prospect.query.get(prospect_id)
    prospect_referred.status = ProspectStatus.QUEUED_FOR_OUTREACH
    prospect_referred.approved_outreach_message_id = generated_message_id
    db.session.add(prospect_referred)
    db.session.commit()

    return generated_message_id


def send_li_referral_outreach_connection(prospect_id: int, message: str) -> bool:
    """Sends a LinkedIn outreach connection message to a referred prospect.

    Args:
        prospect_id: The ID of the referred prospect to send the message to.
        message: The message to send to the referred rrospect.

    Returns:
        True if the message was successfully queued, False otherwise.
    """

    # Send outreach
    generated_message_id = send_li_outreach_connection(
        prospect_id=prospect_id, message=message
    )

    # Grab the ProspectReferral record in order to get the referring prospect
    referral_record: ProspectReferral = ProspectReferral.query.filter(
        ProspectReferral.referred_id == prospect_id
    ).first()
    if not referral_record:
        raise Exception(
            "No referral record found for prospect_id: {}".format(prospect_id)
        )
    prospect_referring: Prospect = Prospect.query.get(referral_record.referral_id)
    prospect_referred: Prospect = Prospect.query.get(prospect_id)

    # Grab the ClientSDR and the Archetype
    client_sdr: ClientSDR = ClientSDR.query.get(prospect_referring.client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(
        prospect_referring.archetype_id
    )
    client: Client = Client.query.get(client_sdr.client_id)

    # Send a Slack message notifying that a message has been queued for outreach for the referred prospect
    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    message_to_referred = gm.completion
    send_slack_message(
        message=f"SellScale just multi-threaded",
        webhook_urls=[
            URL_MAP["company-pipeline"],
            client.pipeline_notifications_webhook_url,
        ],
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🧵 SellScale just multi-threaded",
                    "emoji": True,
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "SellScale is reaching out to *{referred_name} ({referred_company})* through a referral from *{referral_name} ({referral_company})* on behalf of *{sdr_name}* for *{archetype_name}*".format(
                            referral_name=prospect_referring.full_name,
                            referral_company=prospect_referring.company,
                            referred_name=prospect_referred.full_name,
                            referred_company=prospect_referred.company,
                            sdr_name=client_sdr.name,
                            archetype_name=archetype.archetype,
                        ),
                    }
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*😴 Original Contact*: {referral_name} ({referral_company})\n*Message from Contact*: ```{referral_message}```".format(
                        referral_name=prospect_referring.full_name,
                        referral_company=prospect_referring.company,
                        referral_message=prospect_referring.li_last_message_from_prospect,
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🆕 New Contact*: {referred_name} ({referred_company})\n*Outreach to new contact*: ```{referred_message}```".format(
                        referred_name=prospect_referred.full_name,
                        referred_company=prospect_referred.company,
                        referred_message=message_to_referred,
                    ),
                },
            },
        ],
    )

    return True


def add_prospect_referral(referral_id: int, referred_id: int, meta_data=None) -> bool:
    """Adds a ProspectReferral record to the database

    Args:
        referral_id (int): The ID of the Prospect who referred the other Prospect
        referred_id (int): The ID of the Prospect who was referred
        meta_data (dict, optional): Any additional metadata to store with the ProspectReferral record. Defaults to None.

    Returns:
        bool: True if the ProspectReferral record was successfully added to the database, False otherwise
    """
    referral = ProspectReferral(
        referral_id=referral_id, referred_id=referred_id, meta_data=meta_data
    )
    db.session.add(referral)
    db.session.commit()

    prospect_referral: Prospect = Prospect.query.get(referral_id)
    prospect_referred: Prospect = Prospect.query.get(referred_id)
    if not prospect_referral or not prospect_referred:
        return False

    # Get ClientSDR and ClientArchetype
    client_sdr: ClientSDR = ClientSDR.query.get(prospect_referral.client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(
        prospect_referral.archetype_id
    )

    # Send a Slack message notifying that a Prospect was referred
    send_slack_message(
        message=f"SellScale just formed a referral association to *{prospect_referred.full_name} ({prospect_referred.company})* from *{prospect_referral.full_name} ({prospect_referral.company})* for SDR *{client_sdr.name}* in the persona *{archetype.archetype}*",
        webhook_urls=[URL_MAP["company-pipeline"]],
    )

    return True


def get_prospects_for_icp(archetype_id: int):

    data = db.session.execute(
        f"""
        select
          count(distinct prospect.id) filter (where prospect.icp_fit_score = 0) "VERY LOW",
          count(distinct prospect.id) filter (where prospect.icp_fit_score = 1) "LOW",
          count(distinct prospect.id) filter (where prospect.icp_fit_score = 2) "MEDIUM",
          count(distinct prospect.id) filter (where prospect.icp_fit_score = 3) "HIGH",
          count(distinct prospect.id) filter (where prospect.icp_fit_score = 4) "VERY HIGH",

          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = 0) "VERY LOW - IDS",
          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = 1) "LOW - IDS",
          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = 2) "MEDIUM - IDS",
          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = 3) "HIGH - IDS",
          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = 4) "VERY HIGH - IDS",

          count(distinct prospect.id) filter (where prospect.icp_fit_score = -3) "QUEUED",
          count(distinct prospect.id) filter (where prospect.icp_fit_score = -2) "CALCULATING",
          count(distinct prospect.id) filter (where prospect.icp_fit_score = -1) "ERROR",

          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = -3) "QUEUED - IDS",
          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = -2) "CALCULATING - IDS",
          array_agg(concat(prospect.full_name, ' -~- ', prospect.company, ' -~- ', prospect.id, ' -~- ', prospect.icp_fit_score, ' -~- ', prospect.icp_fit_score_override, ' -~- ', prospect.in_icp_sample, ' -~- ', prospect.title, ' -~- ', prospect.icp_fit_reason)) filter (where prospect.icp_fit_score = -1) "ERROR - IDS"
        from
          client_archetype
          join prospect on prospect.archetype_id = client_archetype.id
        where client_archetype.id = {archetype_id} and prospect.overall_status != 'REMOVED';
    """
    ).fetchone()

    def separate_data(rows):
        if not rows:
            return []
        result = []
        for row in rows:
            sep = row.split(" -~- ")
            result.append(
                {
                    "full_name": sep[0],
                    "company": sep[1],
                    "id": sep[2] or None,
                    "icp_fit_score": sep[3] or None,
                    "icp_fit_score_override": sep[4] or None,
                    "in_icp_sample": sep[5] or False,
                    "title": sep[6],
                    "icp_fit_reason": sep[7],
                }
            )
        return result

    return {
        "very_low_count": data[0],
        "low_count": data[1],
        "medium_count": data[2],
        "high_count": data[3],
        "very_high_count": data[4],
        "very_low_data": separate_data(data[5]),
        "low_data": separate_data(data[6]),
        "medium_data": separate_data(data[7]),
        "high_data": separate_data(data[8]),
        "very_high_data": separate_data(data[9]),
        "queued_count": data[10],
        "calculating_count": data[11],
        "error_count": data[12],
        "queued_data": separate_data(data[13]),
        "calculating_data": separate_data(data[14]),
        "error_data": separate_data(data[15]),
    }


def get_prospects_for_income_pipeline(client_sdr_id: int):

    data = db.session.execute(
        f"""
        select

          array_agg(concat(prospect.id, ' -~- ', prospect.company, ' -~- ', prospect.company_url, ' -~- ', prospect.full_name, ' -~- ', prospect.title, ' -~- ', prospect.img_url, ' -~- ', 'company_img_url', ' -~- ', prospect.contract_size, ' -~- ', prospect.linkedin_url, ' -~- ', prospect.updated_at, ' -~- ', prospect_email.outreach_status, ' -~- ', prospect.status, ' -~- ', prospect.deactivate_ai_engagement)) filter (where prospect.overall_status = 'ACTIVE_CONVO' and prospect.status != 'ACTIVE_CONVO_SCHEDULING' and (prospect_email.outreach_status != 'SCHEDULING' or prospect_email.outreach_status is null)) "ACTIVE_CONVO",
          array_agg(concat(prospect.id, ' -~- ', prospect.company, ' -~- ', prospect.company_url, ' -~- ', prospect.full_name, ' -~- ', prospect.title, ' -~- ', prospect.img_url, ' -~- ', 'company_img_url', ' -~- ', prospect.contract_size, ' -~- ', prospect.linkedin_url, ' -~- ', prospect.updated_at, ' -~- ', prospect_email.outreach_status, ' -~- ', prospect.status, ' -~- ', prospect.deactivate_ai_engagement)) filter (where prospect.status = 'ACTIVE_CONVO_SCHEDULING' or prospect_email.outreach_status = 'SCHEDULING') "SCHEDULING",
          array_agg(concat(prospect.id, ' -~- ', prospect.company, ' -~- ', prospect.company_url, ' -~- ', prospect.full_name, ' -~- ', prospect.title, ' -~- ', prospect.img_url, ' -~- ', 'company_img_url', ' -~- ', prospect.contract_size, ' -~- ', prospect.linkedin_url, ' -~- ', prospect.updated_at, ' -~- ', prospect_email.outreach_status, ' -~- ', prospect.status, ' -~- ', prospect.deactivate_ai_engagement)) filter (where prospect.status = 'DEMO_SET' or prospect_email.outreach_status = 'DEMO_SET') "DEMO_SET",
          array_agg(concat(prospect.id, ' -~- ', prospect.company, ' -~- ', prospect.company_url, ' -~- ', prospect.full_name, ' -~- ', prospect.title, ' -~- ', prospect.img_url, ' -~- ', 'company_img_url', ' -~- ', prospect.contract_size, ' -~- ', prospect.linkedin_url, ' -~- ', prospect.updated_at, ' -~- ', prospect_email.outreach_status, ' -~- ', prospect.status, ' -~- ', prospect.deactivate_ai_engagement)) filter (where prospect.status = 'DEMO_WON' or prospect_email.outreach_status = 'DEMO_WON') "DEMO_WON",
          array_agg(concat(prospect.id, ' -~- ', prospect.company, ' -~- ', prospect.company_url, ' -~- ', prospect.full_name, ' -~- ', prospect.title, ' -~- ', prospect.img_url, ' -~- ', 'company_img_url', ' -~- ', prospect.contract_size, ' -~- ', prospect.linkedin_url, ' -~- ', prospect.updated_at, ' -~- ', prospect_email.outreach_status, ' -~- ', prospect.status, ' -~- ', prospect.deactivate_ai_engagement)) filter (where prospect.status = 'DEMO_LOSS' or prospect_email.outreach_status = 'DEMO_LOST' or prospect.status = 'NOT_INTERESTED' or prospect_email.outreach_status = 'NOT_INTERESTED') "NOT_INTERESTED"

        from
          prospect
          left join prospect_email on prospect.id = prospect_email.prospect_id
        where prospect.client_sdr_id = {client_sdr_id} and prospect.overall_status != 'SENT_OUTREACH' and prospect.overall_status != 'PROSPECTED';
    """
    ).fetchone()

    def separate_data(rows):
        if not rows:
            return []
        result = []
        for row in rows:
            sep = row.split(" -~- ")
            result.append(
                {
                    "id": sep[0] or None,
                    "company_name": sep[1] or None,
                    "company_url": sep[2] or None,
                    "full_name": sep[3] or None,
                    "title": sep[4] or None,
                    "img_url": sep[5] or False,
                    "company_img_url": sep[6] or None,
                    "contract_size": sep[7] or None,
                    "li_url": sep[8] or None,
                    "last_updated": sep[9] or None,
                    "email_status": sep[10] or None,
                    "li_status": sep[11] or None,
                    "deactivate_ai_engagement": sep[12] or None,
                }
            )
        return result

    return {
        "active_convo": separate_data(data[0]),
        "scheduling": separate_data(data[1]),
        "demo_set": separate_data(data[2]),
        "demo_won": separate_data(data[3]),
        "not_interested": separate_data(data[4]),
    }


def add_existing_contact(
    client_sdr_id: int,
    connection_source: str,
    full_name: str,
    first_name: Optional[str],
    last_name: Optional[str],
    title: Optional[str],
    bio: Optional[str],
    linkedin_url: Optional[str],
    instagram_url: Optional[str],
    facebook_url: Optional[str],
    twitter_url: Optional[str],
    email: Optional[str],  # Unique
    phone: Optional[str],
    address: Optional[str],
    li_public_id: Optional[str],  # Unique
    li_urn_id: Optional[str],  # Unique
    img_url: Optional[str],
    img_expire: Optional[int],
    industry: Optional[str],
    company_name: Optional[str],
    company_id: Optional[str],
    linkedin_followers: Optional[int],
    instagram_followers: Optional[int],
    facebook_followers: Optional[int],
    twitter_followers: Optional[int],
    notes: Optional[str],
) -> Optional[int]:
    """
    Adds an existing contact to the database.

    Returns the existing contact id.
    """

    from src.individual.services import add_individual
    from src.individual.models import Individual
    from src.prospecting.models import ExistingContact

    individual_id, created = add_individual(
        full_name=full_name,
        first_name=first_name,
        last_name=last_name,
        title=title,
        bio=bio,
        linkedin_url=linkedin_url,
        instagram_url=instagram_url,
        facebook_url=facebook_url,
        twitter_url=twitter_url,
        email=email,
        phone=phone,
        address=address,
        li_public_id=linkedin_url.split("/in/")[1].split("/")[0]
        if linkedin_url
        else li_public_id,
        li_urn_id=li_urn_id,
        img_url=img_url,
        img_expire=img_expire,
        industry=industry,
        company_name=company_name,
        company_id=company_id,
        linkedin_followers=linkedin_followers,
        instagram_followers=instagram_followers,
        facebook_followers=facebook_followers,
        twitter_followers=twitter_followers,
    )
    individual: Individual = Individual.query.get(individual_id)
    if not individual:
        send_slack_message(
            message=f"Failed to create or update an individual for the creation of an existing contact {full_name} ({email})",
            webhook_urls=[URL_MAP["csm-individuals"]],
        )
        return None

    # See if the existing contact already exists
    existing_contact: ExistingContact = ExistingContact.query.filter(
        ExistingContact.client_sdr_id == client_sdr_id,
        ExistingContact.individual_id == individual_id,
    ).first()
    if existing_contact:
        return existing_contact.id

    existing_contact = ExistingContact(
        client_sdr_id=client_sdr_id,
        full_name=individual.full_name,
        title=individual.title,
        individual_id=individual.id,
        company_name=individual.company_name,
        company_id=individual.company_id,
        connection_source=connection_source,
        notes=notes,
    )
    db.session.add(existing_contact)
    db.session.commit()

    return existing_contact.id


def get_existing_contacts(client_sdr_id: int, limit: int, offset: int, search: str):

    from src.prospecting.models import ExistingContact

    existing_contacts: List[ExistingContact] = (
        ExistingContact.query.filter(
            ExistingContact.client_sdr_id == client_sdr_id,
            or_(
                ExistingContact.company_name.ilike(f"%{search}%"),
                ExistingContact.full_name.ilike(f"%{search}%"),
                ExistingContact.title.ilike(f"%{search}%"),
            ),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )

    total_rows: int = ExistingContact.query.filter(
        ExistingContact.client_sdr_id == client_sdr_id,
        or_(
            ExistingContact.company_name.ilike(f"%{search}%"),
            ExistingContact.full_name.ilike(f"%{search}%"),
            ExistingContact.title.ilike(f"%{search}%"),
        ),
    ).count()

    return [c.to_dict() for c in existing_contacts], total_rows


def add_existing_contacts_to_persona(persona_id: int, contact_ids: list[int]):

    from src.prospecting.models import ExistingContact, ProspectStatus

    added_count = 0
    for contact_id in contact_ids:

        existing_contact: ExistingContact = ExistingContact.query.get(contact_id)
        if not existing_contact:
            continue
        contact_data = existing_contact.to_dict()
        li_public_id = contact_data.get("individual_data", {}).get("li_public_id", None)
        if not li_public_id:
            continue

        success = create_prospects_from_linkedin_link_list(
            url_string=f"https://www.linkedin.com/in/{li_public_id}/",
            archetype_id=persona_id,
            set_status=ProspectStatus.ACCEPTED,
            set_note=f"Added from existing contact {existing_contact.full_name} ({existing_contact.company_name})",
        )
        if success:
            existing_contact.used = True
            db.session.commit()
            added_count += 1

    return added_count


def prospect_removal_check_from_csv_payload(
    csv_payload: list, client_sdr_id: int, bulk_remove: bool = False
):
    total_prospect_ids = [
        int(x["Id"]) for x in csv_payload if x["Included"].lower() == "false"
    ]
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(total_prospect_ids),
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.overall_status.notin_(
            [ProspectOverallStatus.REMOVED, ProspectOverallStatus.DEMO]
        ),
    ).all()

    prospect_data = [
        {"id": x.id, "name": x.full_name, "title": x.title, "company": x.company}
        for x in prospects
    ]

    if bulk_remove:
        bulk_updates = []
        ids = [x["id"] for x in prospect_data]
        prospects_for_removal = Prospect.query.filter(Prospect.id.in_(ids)).all()
        for prospect in prospects_for_removal:
            prospect.overall_status = ProspectOverallStatus.REMOVED
            prospect.status = ProspectStatus.NOT_QUALIFIED

            bulk_updates.append(prospect)
        db.session.bulk_save_objects(bulk_updates)
        db.session.commit()

    return prospect_data


def get_li_message_from_contents(
    client_sdr_id: int, prospect_id: int, message: str
) -> Optional[int]:
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return None
    msg: LinkedinConversationEntry = LinkedinConversationEntry.query.filter(
        LinkedinConversationEntry.first_name == prospect.first_name,
        LinkedinConversationEntry.last_name == prospect.last_name,
        LinkedinConversationEntry.connection_degree == "1st",
        LinkedinConversationEntry.message == message.strip(),
    ).first()
    if not msg:
        return None
    return msg.id


def add_prospect_message_feedback(
    client_sdr_id: int,
    prospect_id: int,
    li_msg_id: Optional[int],
    email_msg_id: Optional[int],
    rating: int,
    feedback: str,
) -> int:

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    prospect: Prospect = Prospect.query.get(prospect_id)

    message = ""
    message_id = "Unknown"
    if li_msg_id:
        li_msg: LinkedinConversationEntry = LinkedinConversationEntry.query.get(
            li_msg_id
        )
        message = li_msg.message
        message_id = str(li_msg.id) + ", LinkedIn"
    elif email_msg_id:
        email_msg: EmailConversationMessage = EmailConversationMessage.query.get(
            email_msg_id
        )
        message = email_msg.body
        message_id = str(email_msg.id) + ", Email"

    ratingEmoji = "👍" if rating >= 2 else "👎"

    send_slack_message(
        message=f"Message Feedback: Rating {ratingEmoji} from SDR '{client_sdr.name}'",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message Feedback*: Rating {ratingEmoji} from SDR '{client_sdr.name}'",
                },
            },
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Feedback*"}},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{feedback}```"},
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Message*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"```{message}```"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Sent to '{prospect.full_name}' (#{prospect.id}, msg ID #{message_id})",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Dashboard", "emoji": True},
                    "value": "dashboard_url_link",
                    "url": f"https://app.sellscale.com/authenticate?stytch_token_type=direct&token={client_sdr.auth_token}&redirect=all/contacts/{prospect.id}",
                    "action_id": "button-action",
                },
            },
        ],
        webhook_urls=[URL_MAP["csm-msg-feedback"]],
    )

    feedback = ProspectMessageFeedback(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        li_msg_id=li_msg_id,
        email_msg_id=email_msg_id,
        rating=rating,
        feedback=feedback,
    )
    db.session.add(feedback)
    db.session.commit()

    return feedback.id
