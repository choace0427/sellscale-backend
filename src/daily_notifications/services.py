from app import db, celery
from src.daily_notifications.models import DailyNotification
from src.prospecting.models import Prospect
from src.client.models import ClientSDR
from src.li_conversation.models import LinkedinConversationEntry
from src.utils.datetime.dateutils import get_datetime_now
from datetime import datetime, timedelta


def update_daily_notification_status(id: str, status: str):
    """Updates the status of the daily notification with id to status.

    Args:
        daily_notification_id (int): ID of the DailyNotification
        status (str): Either 'COMPLETE', 'CANCELLED', or 'PENDING'

    Returns:
        HTTPS response: 200 if successful.
    """
    db.session.query(DailyNotification).filter_by(id=id).update({"status": status})
    db.session.commit()

    return 'OK', 200


@celery.task
def fill_in_daily_notifications():
    """Finds all prospects with unread messages and creates a daily notification for them.

    Returns:
        HTTPS response: 200 if successful.
    """

    for client_sdr in ClientSDR.query.all():
        
        prospects = db.session.query(Prospect).filter_by(client_sdr_id=client_sdr.id).filter_by(status='ACTIVE_CONVO').all()
        for prospect in prospects:

            latest_message = db.session.query(LinkedinConversationEntry).filter_by(conversation_url=prospect.li_conversation_thread_id).order_by(LinkedinConversationEntry.date.desc()).first()
            
            print(latest_message, latest_message.connection_degree)

            if latest_message.connection_degree != 'You':

                # create daily notification
                daily_notification = DailyNotification(
                    prospect_id=prospect.id,
                    client_sdr_id=client_sdr.id,
                    status='PENDING',
                    title='Unread message from {prospect_name}'.format(prospect_name=prospect.full_name),
                    description='Reply to {prospect_name} and update their status if necessary'.format(prospect_name=prospect.full_name),
                    due_date=get_datetime_now() + timedelta(days=1) # 1 day from now
                )
                db.session.add(daily_notification)

    db.session.commit()

    return 'OK', 200


@celery.task
def clear_daily_notifications():
    """Clears all daily notifications that are more than 7 days old.

    Returns:
        HTTPS response: 200 if successful.
    """

    for daily_notification in db.session.query(DailyNotification).all():
        # Check if it's more than 7 days old
        if daily_notification.due_date < get_datetime_now() - timedelta(days=7):
            db.session.delete(daily_notification)

    db.session.commit()

    return 'OK', 200
