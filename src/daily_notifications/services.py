from app import db, celery
from src.daily_notifications.models import DailyNotification, NotificationType, EngagementFeedItem, EngagementFeedType
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

def update_daily_notification_status(client_sdr_id: str, prospect_id: str, type: NotificationType, status: str):
    """Updates the status of the daily notification with id to status.

    Args:
        client_sdr_id (str): ID of the client SDR
        prospect_id (str): ID of the prospect, or -1 for none
        type (NotificationType): Type of the notification
        status (str): Either 'COMPLETE', 'CANCELLED', or 'PENDING'

    Returns:
        HTTPS response: 200 if successful.
    """
    db.session.query(DailyNotification).filter_by(client_sdr_id=client_sdr_id, prospect_id=prospect_id, type=type).update({"status": status})
    db.session.commit()

    return 'OK', 200


@celery.task
def fill_in_daily_notifications():
    """Finds all prospects with unread messages and creates a daily notification for them.

    Returns:
        HTTPS response: 201 if successful.
    """

    send_slack_message(
        message='Running fill_in_daily_notifications!',
        webhook_urls=[URL_MAP['eng-sandbox']]
    )

    for client_sdr in ClientSDR.query.all():

        add_unread_messages(client_sdr)
        add_schedulings(client_sdr)

    db.session.commit()

    return 'Created', 201


def add_unread_messages(client_sdr):
    """Adds unread messages to the daily notifications table.
    """

    prospects = db.session.query(Prospect).filter_by(client_sdr_id=client_sdr.id).filter_by(status='ACTIVE_CONVO').all()
    for prospect in prospects:

        latest_message = db.session.query(LinkedinConversationEntry).filter_by(conversation_url=prospect.li_conversation_thread_id).order_by(LinkedinConversationEntry.date.desc()).first()

        if latest_message and latest_message.connection_degree != 'You':

            existing_record = DailyNotification.query.filter_by(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type='UNREAD_MESSAGE',
            ).first()

            # create daily notification
            daily_notification = DailyNotification(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type='UNREAD_MESSAGE',
                title='Unread message from {prospect_name}'.format(prospect_name=prospect.full_name),
                description='Reply to {prospect_name} and update their status if necessary'.format(prospect_name=prospect.full_name),
                status='PENDING',
                due_date=get_datetime_now() + timedelta(days=DUE_DATE_DAYS) # DUE_DATE_DAYS days from now
            )

            # If it's non-existent, cancelled, or complete, we want to create a new one
            if not existing_record:
                db.session.add(daily_notification)
            elif existing_record.status.value == 'CANCELLED' or existing_record.status.value == 'COMPLETE':
                db.session.merge(daily_notification)


def add_schedulings(client_sdr):
    """Adds schedulings to the daily notifications table.
    """

    prospects = db.session.query(Prospect).filter_by(client_sdr_id=client_sdr.id).filter_by(status='SCHEDULING').all()
    for prospect in prospects:

        latest_message = db.session.query(LinkedinConversationEntry).filter_by(conversation_url=prospect.li_conversation_thread_id).order_by(LinkedinConversationEntry.date.desc()).first()

        # If the latest message is older than SCHEDULING_CHECK_DAYS days, create a daily notification
        if latest_message and latest_message.updated_at < get_datetime_now() - timedelta(days=SCHEDULING_CHECK_DAYS):

            existing_record = DailyNotification.query.filter_by(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type='SCHEDULING',
            ).first()

            # create daily notification
            daily_notification = DailyNotification(
                client_sdr_id=client_sdr.id,
                prospect_id=prospect.id,
                type='SCHEDULING',
                title='Previous scheduling with {prospect_name}'.format(prospect_name=prospect.full_name),
                description='Follow up with {prospect_name} and update their status if necessary'.format(prospect_name=prospect.full_name),
                status='PENDING',
                due_date=get_datetime_now() + timedelta(days=DUE_DATE_DAYS) # DUE_DATE_DAYS days from now
            )

            # If it's non-existent, cancelled, or complete, we want to create a new one
            if not existing_record:
                db.session.add(daily_notification)
            elif existing_record.status.value == 'CANCELLED' or existing_record.status.value == 'COMPLETE':
                db.session.merge(daily_notification)


@celery.task
def clear_daily_notifications():
    """Clears all daily notifications that are more than 7 days old.

    Returns:
        HTTPS response: 200 if successful.
    """

    send_slack_message(
        message='Running clear_daily_notifications!',
        webhook_urls=[URL_MAP['eng-sandbox']]
    )

    for daily_notification in db.session.query(DailyNotification).all():
        # Check if it's more than CLEAR_DAYS days old
        if daily_notification.due_date < get_datetime_now() - timedelta(days=CLEAR_DAYS):
            db.session.delete(daily_notification)

    db.session.commit()

    return 'OK', 200


def create_engagement_feed_item(client_sdr_id: int, prospect_id: int, channel_type: str, engagement_type: str, engagement_metadata: Optional[dict] = None) -> int:
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


def get_engagement_feed_items(client_sdr_id: int, limit: Optional[int] = 10, offset: Optional[int] = 0) -> list[dict]:
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

    engagement_feed_items: list[EngagementFeedItem] = EngagementFeedItem.query.filter_by(
        client_sdr_id=client_sdr_id
    ).order_by(
        EngagementFeedItem.created_at.desc()
    ).limit(limit).offset(offset).all()

    better_ef_item_list = []
    for ef_item in engagement_feed_items:
        item = ef_item.to_dict()
        item['archetype_name'] = None
        item['prospect_name'] = None
        item['prospect_title'] = None
        item['prospect_company'] = None
        item['prospect_img_url'] = None
        item['sdr_img_url'] = img_url

        prospect_id = item.get('prospect_id')
        if prospect_id:
            prospect: Prospect = Prospect.query.get(item['prospect_id'])
            archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
            if archetype:
                item['archetype_name'] = archetype.archetype
            if prospect:
                item['prospect_name'] = prospect.full_name
                item['prospect_title'] = prospect.title
                item['prospect_company'] = prospect.company
                item['prospect_img_url'] = prospect.img_url

        better_ef_item_list.append(item)


    return better_ef_item_list
