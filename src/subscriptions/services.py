from datetime import datetime
from typing import Optional
from app import db
from src.subscriptions.models import Subscription


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


def activate_subscription(subscription_id: int) -> None:
    """Activate a subscription

    Args:
        subscription_id (int): The ID of the subscription to activate
    """
    # Get the subscription
    subscription: Subscription = Subscription.query.filter_by(
        id=subscription_id
    ).first()

    # Activate the subscription
    subscription.active = True
    subscription.deactivation_date = None
    db.session.commit()

    return


def deactivate_subscription(subscription_id: int) -> None:
    """Deactivate a subscription

    Args:
        subscription_id (int): The ID of the subscription to deactivate
    """
    # Get the subscription
    subscription: Subscription = Subscription.query.filter_by(
        id=subscription_id
    ).first()

    # Deactivate the subscription
    subscription.active = False
    subscription.deactivation_date = datetime.utcnow()
    db.session.commit()

    return
