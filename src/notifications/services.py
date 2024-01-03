from src.notifications.models import OperatorNotification, OperatorNotificationPriority
from app import db


def create_notification(
    client_sdr_id: int,
    title: str,
    subtitle: str,
    stars: int,
    cta: str,
    data: dict,
    priority: OperatorNotificationPriority,
):
    notification = OperatorNotification(
        client_sdr_id=client_sdr_id,
        title=title,
        subtitle=subtitle,
        stars=stars,
        cta=cta,
        data=data,
        priority=priority,
    )
    db.session.add(notification)
    db.session.commit()

    return True


def get_notifications_for_sdr(sdr_id: int):
    notifications = (
        OperatorNotification.query.filter_by(client_sdr_id=sdr_id)
        .order_by(OperatorNotification.priority)
        .all()
    )
    return [notification.to_dict() for notification in notifications]
