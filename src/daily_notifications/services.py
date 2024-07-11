import datetime
from operator import or_
from app import db, celery
from src.daily_notifications.models import (
    DailyNotification,
    NotificationType,
    EngagementFeedItem,
    EngagementFeedType,
)
from src.prospecting.models import ProspectStatus
from src.prospecting.models import Prospect
from src.client.models import ClientSDR, ClientArchetype
from src.li_conversation.models import LinkedinConversationEntry
from src.utils.datetime.dateutils import get_datetime_now
from datetime import timedelta
from src.utils.slack import send_slack_message, URL_MAP
from typing import Optional

DUE_DATE_DAYS = 1
CLEAR_DAYS = 7
SCHEDULING_CHECK_DAYS = 2


def update_daily_notification_status(
    client_sdr_id: str, prospect_id: str, type: NotificationType, status: str
):
    """Updates the status of the daily notification with id to status.

    Args:
        client_sdr_id (str): ID of the client SDR
        prospect_id (str): ID of the prospect, or -1 for none
        type (NotificationType): Type of the notification
        status (str): Either 'COMPLETE', 'CANCELLED', or 'PENDING'

    Returns:
        HTTPS response: 200 if successful.
    """
    db.session.query(DailyNotification).filter_by(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id, type=type
    ).update({"status": status})
    db.session.commit()

    return "OK", 200


@celery.task
def fill_in_daily_notifications():
    """Finds all prospects with unread messages and creates a daily notification for them.

    Returns:
        HTTPS response: 201 if successful.
    """

    send_slack_message(
        message="Running fill_in_daily_notifications!",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    for client_sdr in ClientSDR.query.all():
        add_unread_messages(client_sdr)
        add_schedulings(client_sdr)

    db.session.commit()

    return "Created", 201


def add_unread_messages(client_sdr):
    """Adds unread messages to the daily notifications table."""

    prospects = (
        db.session.query(Prospect)
        .filter_by(client_sdr_id=client_sdr.id)
        .filter_by(status="ACTIVE_CONVO")
        .all()
    )
    for prospect in prospects:
        latest_message = (
            db.session.query(LinkedinConversationEntry)
            .filter_by(conversation_url=prospect.li_conversation_thread_id)
            .order_by(LinkedinConversationEntry.date.desc())
            .first()
        )

        if latest_message and latest_message.connection_degree != "You":
            existing_record = DailyNotification.query.filter_by(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type="UNREAD_MESSAGE",
            ).first()

            # create daily notification
            daily_notification = DailyNotification(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type="UNREAD_MESSAGE",
                title="Unread message from {prospect_name}".format(
                    prospect_name=prospect.full_name
                ),
                description="Reply to {prospect_name} and update their status if necessary".format(
                    prospect_name=prospect.full_name
                ),
                status="PENDING",
                due_date=get_datetime_now()
                + timedelta(days=DUE_DATE_DAYS),  # DUE_DATE_DAYS days from now
            )

            # If it's non-existent, cancelled, or complete, we want to create a new one
            if not existing_record:
                db.session.add(daily_notification)
            elif (
                existing_record.status.value == "CANCELLED"
                or existing_record.status.value == "COMPLETE"
            ):
                db.session.merge(daily_notification)


def add_schedulings(client_sdr):
    """Adds schedulings to the daily notifications table."""

    prospects = (
        db.session.query(Prospect)
        .filter_by(client_sdr_id=client_sdr.id)
        .filter_by(status="SCHEDULING")
        .all()
    )
    for prospect in prospects:
        latest_message = (
            db.session.query(LinkedinConversationEntry)
            .filter_by(conversation_url=prospect.li_conversation_thread_id)
            .order_by(LinkedinConversationEntry.date.desc())
            .first()
        )

        # If the latest message is older than SCHEDULING_CHECK_DAYS days, create a daily notification
        if (
            latest_message
            and latest_message.updated_at
            < get_datetime_now() - timedelta(days=SCHEDULING_CHECK_DAYS)
        ):
            existing_record = DailyNotification.query.filter_by(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type="SCHEDULING",
            ).first()

            # create daily notification
            daily_notification = DailyNotification(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type="SCHEDULING",
                title="Previous scheduling with {prospect_name}".format(
                    prospect_name=prospect.full_name
                ),
                description="Follow up with {prospect_name} and update their status if necessary".format(
                    prospect_name=prospect.full_name
                ),
                status="PENDING",
                due_date=get_datetime_now()
                + timedelta(days=DUE_DATE_DAYS),  # DUE_DATE_DAYS days from now
            )

            # If it's non-existent, cancelled, or complete, we want to create a new one
            if not existing_record:
                db.session.add(daily_notification)
            elif (
                existing_record.status.value == "CANCELLED"
                or existing_record.status.value == "COMPLETE"
            ):
                db.session.merge(daily_notification)


@celery.task
def clear_daily_notifications():
    """Clears all daily notifications that are more than 7 days old.

    Returns:
        HTTPS response: 200 if successful.
    """

    send_slack_message(
        message="Running clear_daily_notifications!",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    for daily_notification in db.session.query(DailyNotification).all():
        # Check if it's more than CLEAR_DAYS days old
        if daily_notification.due_date < get_datetime_now() - timedelta(
            days=CLEAR_DAYS
        ):
            db.session.delete(daily_notification)

    db.session.commit()

    return "OK", 200


def create_engagement_feed_item(
    client_sdr_id: int,
    prospect_id: int,
    channel_type: str,
    engagement_type: str,
    engagement_metadata: Optional[dict] = None,
) -> int:
    """Adds an engagement feed item to the daily notifications table.

    Args:
        client_sdr_id (int): Client SDR ID
        prospect_id (int): Prospect ID
        channel_type (str): Channel of the engagement
        engagement_type (str): Type of engagement
        engagement_metadata (dict): Engagement metadata

    Returns:
        int: Engagement feed item ID
    """
    new_item = EngagementFeedItem(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        channel_type=channel_type,
        engagement_type=engagement_type,
        viewed=False,
        engagement_metadata=engagement_metadata,
    )
    db.session.add(new_item)
    db.session.commit()

    return new_item.id


def get_engagement_feed_items_for_prospect(prospect_id: int) -> list[dict]:
    """Gets engagement feed items for a prospect.

    Args:
        prospect_id (int): Prospect ID

    Returns:
        list[dict]: Engagement feed items
    """
    engagement_feed_items: list[EngagementFeedItem] = (
        EngagementFeedItem.query.filter_by(prospect_id=prospect_id).order_by(
            EngagementFeedItem.created_at.desc()
        )
    ).all()
    prospect: Prospect = Prospect.query.get(prospect_id)

    better_ef_item_list = []
    for ef_item in engagement_feed_items:
        item = ef_item.to_dict()
        item["archetype_name"] = None
        item["client_sdr_name"] = None
        item["client_sdr_img_url"] = None

        client_sdr_id = item.get("client_sdr_id")
        if client_sdr_id:
            client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )
            if archetype:
                item["archetype_name"] = archetype.archetype
            if client_sdr:
                item["client_sdr_name"] = client_sdr.name
                item["client_sdr_img_url"] = client_sdr.img_url

        better_ef_item_list.append(item)

    return better_ef_item_list


def get_engagement_feed_items_for_sdr(
    client_sdr_id: int, limit: Optional[int] = 10, offset: Optional[int] = 0
) -> tuple[int, list[dict]]:
    """Gets engagement feed items for a client SDR.

    Args:
        client_sdr_id (int): Client SDR ID
        limit (int): Number of items to return
        offset (int): Offset

    Returns:
        list[dict]: Engagement feed items
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    img_url = sdr.img_url

    engagement_feed_items: list[
        EngagementFeedItem
    ] = EngagementFeedItem.query.filter_by(client_sdr_id=client_sdr_id).order_by(
        EngagementFeedItem.created_at.desc()
    )
    total_count = engagement_feed_items.count()
    engagement_feed_items = engagement_feed_items.limit(limit).offset(offset).all()

    better_ef_item_list = []
    for ef_item in engagement_feed_items:
        item = ef_item.to_dict()
        item["archetype_name"] = None
        item["prospect_name"] = None
        item["prospect_title"] = None
        item["prospect_company"] = None
        item["prospect_img_url"] = None
        item["sdr_img_url"] = img_url

        prospect_id = item.get("prospect_id")
        if prospect_id:
            prospect: Prospect = Prospect.query.get(item["prospect_id"])
            archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )
            if archetype:
                item["archetype_name"] = archetype.archetype
            if prospect:
                item["prospect_name"] = prospect.full_name
                item["prospect_title"] = prospect.title
                item["prospect_company"] = prospect.company
                item["prospect_img_url"] = prospect.img_url

        better_ef_item_list.append(item)

    return total_count, better_ef_item_list
def get_positive_responses(client_sdr_id: int) -> list[dict]:
    """Gets positive message responses for a client SDR within the last month.

    Args:
        client_sdr_id (int): Client SDR ID

    Returns:
        list[dict]: Prospects with positive message responses including messages, full name, prospect ID, and date
    """
    
    client_id = ClientSDR.query.get(client_sdr_id).client_id
    
    query = """
    select 
        prospect.id,
        prospect.full_name,
        max(case
            when prospect_status_records.created_at is not null then prospect_status_records.created_at
            when prospect_email_status_records.created_at is not null then prospect_email_status_records.created_at
            else now()
        end) as date_created,
        case
            when prospect_status_records.created_at is not null then cast(prospect_status_records.to_status as varchar)
            when prospect_email_status_records.created_at is not null then cast(prospect_email_status_records.to_status as varchar)
            else ''
        end as to_status,
        case
            when prospect_status_records.created_at is not null then prospect.li_last_message_from_prospect
            when prospect_email_status_records.created_at is not null then prospect.email_last_message_from_prospect
            else ''
        end as last_msg,
        client_sdr.auth_token
    from prospect
        join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        left join prospect_email on prospect_email.prospect_id = prospect.id
        left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
        join client_sdr on client_sdr.id = prospect.client_sdr_id
    where
        (
            prospect_email_status_records.to_status = 'DEMO_SET'
            or prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION')
        )
        and prospect.client_id = :client_id
        and prospect.overall_status in ('ACTIVE_CONVO')
        and (
            prospect_email_status_records.created_at > NOW() - interval '1 month'
            or
            prospect_status_records.created_at > NOW() - interval '1 month'
        )
    group by 1,2,4,5,6;
    """
    
    results = db.session.execute(query, {'client_id': client_id}).fetchall()
    
    positive_responses = []
    for row in results:
        positive_responses.append({
            'prospect_id': row['id'],
            'full_name': row['full_name'],
            'date': row['date_created'],
            'to_status': row['to_status'],
            'last_msg': row['last_msg'],
            'auth_token': row['auth_token'],
        })
    
    return positive_responses