from app import db
from sqlalchemy.orm import attributes
from sqlalchemy import or_
from model_import import Prospect, ProspectStatus, ClientSDR, Client
from datetime import datetime, timedelta

RECORD_BUMP = "RECORD_BUMP"
NOT_INTERESTED = "NOT_INTERESTED"
ACTIVE_CONVO = "ACTIVE_CONVO"
SCHEDULING = "SCHEDULING"
DEMO_SET = "DEMO_SET"
INTERVENTION_NEEDED = "INTERVENTION_NEEDED"

DATE_TO_REVIEW_WINDOW = 3
DATE_TO_REVIEW_FOR_ACTIVE_CONVOS = 1


def get_actions(prospect_status: ProspectStatus):
    if prospect_status == ProspectStatus.ACCEPTED:
        return [RECORD_BUMP, NOT_INTERESTED]
    elif prospect_status == ProspectStatus.RESPONDED:
        return [RECORD_BUMP, NOT_INTERESTED, ACTIVE_CONVO, INTERVENTION_NEEDED]
    elif prospect_status == ProspectStatus.ACTIVE_CONVO:
        return [RECORD_BUMP, NOT_INTERESTED, SCHEDULING, DEMO_SET, INTERVENTION_NEEDED]
    elif prospect_status == ProspectStatus.SCHEDULING:
        return [RECORD_BUMP, DEMO_SET, INTERVENTION_NEEDED, NOT_INTERESTED]

    return []


def map_prospect(prospect: Prospect):
    client_sdr_id: int = prospect.client_sdr_id
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(prospect.client_id)
    return {
        "prospect_id": prospect.id,
        "prospect_full_name": prospect.full_name,
        "prospect_title": prospect.title,
        "prospect_linkedin": prospect.linkedin_url,
        "prospect_linkedin_conversation_thread": prospect.li_conversation_thread_id,
        "prospect_sdr_name": client_sdr.name,
        "prospect_client_name": client.company,
        "prospect_archetype_id": prospect.archetype_id,
        "prospect_last_reviwed_date": prospect.last_reviewed,
        "prospect_status": prospect.status.value,
        "actions": get_actions(prospect.status),
        "prospect_deactivate_ai_engagement": prospect.deactivate_ai_engagement,
        "prospect_last_message_from": prospect.li_last_message_from_prospect,
    }


def get_all_accepted_prospects(client_sdr_id: int):
    prospects: list = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.status == ProspectStatus.ACCEPTED,
    ).all()
    return [map_prospect(p) for p in prospects]


def get_all_bumped_prospects(client_sdr_id: int):
    prospects: list = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.status == ProspectStatus.RESPONDED,
        or_(
            Prospect.last_reviewed
            < datetime.now() - timedelta(days=DATE_TO_REVIEW_WINDOW),
            Prospect.last_reviewed.is_(None),
        ),
    ).all()
    return [map_prospect(p) for p in prospects]


def get_all_active_convo_prospects(client_sdr_id: int):
    prospects: list = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.status == ProspectStatus.ACTIVE_CONVO,
        or_(
            Prospect.last_reviewed
            < datetime.now() - timedelta(days=DATE_TO_REVIEW_FOR_ACTIVE_CONVOS),
            Prospect.last_reviewed.is_(None),
        ),
    ).all()
    return [map_prospect(p) for p in prospects]


def get_all_scheduling_prospects(client_sdr_id: int):
    prospects: list = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.status == ProspectStatus.SCHEDULING,
        or_(
            Prospect.last_reviewed
            < datetime.now() - timedelta(days=DATE_TO_REVIEW_WINDOW),
            Prospect.last_reviewed.is_(None),
        ),
    ).all()
    return [map_prospect(p) for p in prospects]


def get_outstanding_inbox(client_sdr_id: int):
    """Returns a list of outstanding inbox items.

    return_value:
    [
        {
            "prospect_id": int,
            "prospect_full_name": str,
            "prospect_title": str,
            "prospect_linkedin": str,
            "prospect_linkedin_conversation_thread": str,
            "prospect_sdr_name": str,
            "prospect_client_name": str,
            "prospect_last_reviwed_date": datetime,
            "prospect_status: ProspectStatus,
            "prospect_deactivate_ai_engagement": bool,
            "prospect_last_message_from": str,
            "prospect_archetype_id": int,


            "actions": RECORD_BUMP | NOT_INTERESTED | ACTIVE_CONVO | SCHEDULING | DEMO_SET,

            "last_message": todo(Aakash) implement this,
            "last_message_timestamp": todo(Aakash) implement this
        }
        ...
    ]

    This will be mapped in SellScale in an inbox view.
    """

    accepted_prospects = get_all_accepted_prospects(client_sdr_id=client_sdr_id)
    bumped_prospects = get_all_bumped_prospects(client_sdr_id=client_sdr_id)
    active_convo_prospects = get_all_active_convo_prospects(client_sdr_id=client_sdr_id)
    scheduling_prospects = get_all_scheduling_prospects(client_sdr_id=client_sdr_id)
    combine_prospect_lists = (
        accepted_prospects
        + bumped_prospects
        + active_convo_prospects
        + scheduling_prospects
    )
    sorted_prospect_lists_by_date = sorted(
        combine_prospect_lists,
        key=lambda prospect: prospect.get("prospect_last_reviwed_date")
        or datetime.now(),
    )

    return sorted_prospect_lists_by_date


def get_inbox_prospects(client_sdr_id: int):
    """
    Returns a list of all prospects in the inbox in a series of buckets:
    - Needs Attention
    - Queued for AI
    - Demo Set
    - CRM Sync
    - Sent Outreach
    - Snoozed
    """

    query = f"""
with d as (
select
prospect.id "prospect_id",
client_sdr.name "client_sdr_name",
prospect.full_name,
prospect.title,
prospect.company,
prospect.overall_status,
prospect.status "status_linkedin",
prospect_email.outreach_status "status_email",
prospect.hidden_until,
prospect.li_last_message_timestamp,
prospect.li_last_message_from_prospect,
prospect.email_last_message_timestamp,
prospect.email_last_message_from_prospect,
prospect.deactivate_ai_engagement
from prospect
join client_sdr on client_sdr.id = prospect.client_sdr_id
left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
where prospect.overall_status in ('DEMO', 'ACTIVE_CONVO', 'SENT_OUTREACH')
and client_sdr_id = {client_sdr_id}
)
select
*
from d;
    """

    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    if result is None:
        return None

    from src.prospecting.services import (
        has_linkedin_auto_reply_disabled,
        has_email_auto_reply_disabled,
    )

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    manual_bucket = []
    ai_bucket = []
    demo_bucket = []
    crm_bucket = []
    outreach_bucket = []
    snoozed_bucket = []

    for row in result:
        if row["hidden_until"] == None or row["hidden_until"] <= datetime.utcnow():
            pass  # it's not snoozed
        else:
            snoozed_bucket.append(row)
            continue

        if row["overall_status"] == "DEMO":
            demo_bucket.append(row)
            continue

        if row["overall_status"] == "SENT_OUTREACH":
            outreach_bucket.append(row)
            continue

        # TODO, crm_bucket

        if has_linkedin_auto_reply_disabled(
            sdr, row["status_linkedin"]
        ) or has_email_auto_reply_disabled(sdr, row["status_email"]):
            manual_bucket.append(row)
        else:
            ai_bucket.append(row)

    return {
        "manual_bucket": manual_bucket,
        "ai_bucket": ai_bucket,
        "demo_bucket": demo_bucket,
        "crm_bucket": crm_bucket,
        "outreach_bucket": outreach_bucket,
        "snoozed_bucket": snoozed_bucket,
    }
