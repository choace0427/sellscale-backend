from datetime import datetime
from typing import Optional
from app import db
from src.slack.models import SlackNotification
from src.subscriptions.models import Subscription


def get_subscriptions(client_sdr_id: int) -> list:
    """Get all subscriptions for a client

    Args:
        client_sdr_id (int): The client SDR ID

    Returns:
        list: A list of all subscriptions for a client
    """
    # Join the Slack Notifications with Subscriptions to return whether or not
    # the SDR is subscribed to each Slack Notification. Convert to dictionary.
    sql_query_slack_subscriptions = (
        db.session.query(
            SlackNotification.id,
            SlackNotification.notification_type,
            SlackNotification.notification_name,
            SlackNotification.notification_description,
            Subscription.id,
            Subscription.active,
        )
        .outerjoin(
            Subscription,
            (SlackNotification.id == Subscription.slack_notification_id)
            & (Subscription.client_sdr_id == client_sdr_id),
        )
        .all()
    )
    slack_subscriptions = []
    for row in sql_query_slack_subscriptions:
        slack_subscriptions.append(
            {
                "id": row[0],
                "notification_type": row[1].value,
                "notification_name": row[2],
                "notification_description": row[3],
                "subscription_id": row[4],
                "subscribed": True if row[5] else False,
            }
        )

    subscriptions = {
        "slack_subscriptions": slack_subscriptions,
    }

    return subscriptions


def subscribe_to_slack_notification(
    client_sdr_id: int, slack_notification_id: int
) -> int:
    """Subscribe a client to a Slack notification

    Args:
        client_sdr_id (int): The client SDR ID
        slack_notification_id (int): The Slack notification ID

    Returns:
        int: The ID of the subscription that was created
    """
    # Check if the subscription already exists
    subscription: Subscription = Subscription.query.filter_by(
        client_sdr_id=client_sdr_id, slack_notification_id=slack_notification_id
    ).first()
    if subscription:
        # If the subscription already exists, then activate it
        activate_subscription(
            client_sdr_id=client_sdr_id, subscription_id=subscription.id
        )
        return subscription.id

    # Create the subscription
    subscription_id = create_subscription(
        client_sdr_id=client_sdr_id,
        slack_notification_id=slack_notification_id,
    )

    return subscription_id


def create_subscription(
    client_sdr_id: int,
    slack_notification_id: Optional[int] = None,
) -> int:
    """Create a subscription

    Args:
        client_sdr_id (int): The client SDR ID
        slack_notification_id (int): The Slack notification ID
        email_newsletter_id (int): The email newsletter ID
        sms_notification_id (int): The SMS notification ID

    Returns:
        int: The ID of the subscription that was created
    """
    if not slack_notification_id:
        raise Exception("Subscriptions can't be created empty")

    # Create the subscription
    subscription = Subscription(
        client_sdr_id=client_sdr_id,
        slack_notification_id=slack_notification_id,
        active=True,
    )
    db.session.add(subscription)
    db.session.commit()

    return subscription.id


def activate_subscription(client_sdr_id: int, subscription_id: int) -> bool:
    """Activate a subscription

    Args:
        client_sdr_id (int): The client SDR ID
        subscription_id (int): The ID of the subscription to activate

    Returns:
        bool: Whether or not the subscription was activated
    """
    # Get the subscription
    subscription: Subscription = Subscription.query.filter_by(
        id=subscription_id,
        client_sdr_id=client_sdr_id,
    ).first()
    if not subscription:
        return False

    # Activate the subscription
    subscription.active = True
    subscription.deactivation_date = None
    db.session.commit()

    return True


def deactivate_subscription(client_sdr_id: int, subscription_id: int) -> bool:
    """Deactivate a subscription

    Args:
        client_sdr_id (int): The client SDR ID
        subscription_id (int): The ID of the subscription to deactivate
    """
    # Get the subscription
    subscription: Subscription = Subscription.query.filter_by(
        id=subscription_id,
        client_sdr_id=client_sdr_id,
    ).first()
    if not subscription:
        return False

    # Deactivate the subscription
    subscription.active = False
    subscription.deactivation_date = datetime.utcnow()
    db.session.commit()

    return True
