import openai
from app import db
from src.daily_notifications.models import DailyNotifications
from src.prospecting.models import Prospect
from src.client.models import ClientSDR
from src.li_conversation.models import LinkedinConversationEntry
from datetime import datetime


def update_daily_notification_status(id: str, status: str):
    """
    Updates the status of the daily notification with id to status.
    """
    db.session.query(DailyNotifications).filter_by(id=id).update({"status": status})
    db.session.commit()


def fill_in_daily_notifications():
    """Finds all prospects with unread messages and creates a daily notification for them.

    Returns:
        HTTPS response: 200 if successful.
    """

    for client_sdr in db.session.query(ClientSDR).all():


        print('Client SDR: {0}'.format(client_sdr.id))
        
        prospects = db.session.query(Prospect).filter_by(client_sdr_id=client_sdr.id).all()
        for prospect in prospects:

            print('Prospect Name: '.format(prospect.name))

            latest_message = db.session.query(LinkedinConversationEntry).order_by(LinkedinConversationEntry.date.desc()).first()
            
            if latest_message.connection_degree != 'You':

                # create daily notification
                daily_notification = DailyNotifications(
                    prospect_id=prospect.id,
                    client_sdr_id=client_sdr.id,
                    status='PENDING',
                    title='Unread message from {prospect_name}'.format(prospect_name=prospect.name),
                    description='Send a message to {prospect_name}.'.format(prospect_name=prospect.name),
                    due_date=datetime.datetime.now()+datetime.timedelta(days=1) # 1 day from now
                )
                db.session.add(daily_notification)

    db.session.commit()

    return 'OK', 200


def clear_daily_notifications():
    """Clears all daily notifications.

    Returns:
        HTTPS response: 200 if successful.
    """

    db.session.query(DailyNotifications).delete()
    db.session.commit()

    return 'OK', 200