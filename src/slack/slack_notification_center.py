# This file contains the functions that are used to send Slack Notifications to Slack Webhook URLs
# - These functions are the wrappers around Slack endpoints that are used to send Slack messages
#
# To create a new Slack Notification, please reference slack_notification.py


# Intended usage and designing of new Slack Notifications
# 1. Create new Slack Notifications in src/slack_notifications/notifications
# 2. Slack Notification should be responsible for constructing the blocks and the message
# 3. Slack Notification should call send_slack_message() from src/slack_notifications/slack.py
#
# How to use Slack Notification blocks: https://api.slack.com/reference/block-kit/blocks
# How to add a Webhook: https://api.slack.com/messaging/webhooks


import os

from app import db, slack_app
from typing import Optional, TypedDict, Union
from slack_sdk.webhook import WebhookClient
from datetime import datetime

from model_import import Client
from src.client.models import ClientSDR
from src.slack.auth.models import SlackAuthentication
from src.slack.channels.models import SlackConnectedChannel
from src.slack.models import (
    SlackNotificationClassLogger,
    SlackNotificationType,
)
from src.slack.slack_notification_class import SlackNotificationClass
from src.subscriptions.models import Subscription


NOTIFICATION_TESTING_CHANNEL = (
    "https://hooks.slack.com/services/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"
)
SLACK_ERROR_CHANNEL = (
    "https://hooks.slack.com/services/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"
)


def create_and_send_slack_notification_class_message(
    notification_type: SlackNotificationType,
    arguments: dict,
) -> bool:
    """Create a Slack Notification and send it. This is used to help track potential errors.

    Args:
        notification_type (SlackNotificationType): The type of the notification that is being sent.
        arguments (dict): The arguments to be passed to the Slack Notification.

    Returns:
        bool: Whether or not the message was successfully sent
    """
    # Create the log entry
    log: SlackNotificationClassLogger = SlackNotificationClassLogger(
        notification_type=notification_type,
        arguments=arguments,
        status="IN_PROGRESS",
    )
    db.session.add(log)
    db.session.commit()

    # Create the Slack Notification
    try:
        slack_notification_class: SlackNotificationClass = (
            notification_type.get_class()(**arguments)
        )
        status = slack_notification_class.send_notification(preview_mode=False)
        if not status:
            log.status = "FAILED"
            log.error = "Something went wrong while sending the Slack notification, something returned False or Null"
            db.session.commit()
            send_slack_error_message(
                type=notification_type.value,
                error="Something went wrong while sending the Slack notification, something returned False or Null",
            )
            return False
    except Exception as e:
        db.session.rollback()
        log.status = "ERROR"
        log.error = str(e)
        db.session.commit()
        return False

    log.status = "SUCCESS"
    db.session.commit()
    return True


class WebhookDict(TypedDict):
    url: str
    channel: str


def slack_bot_send_message(
    notification_type: SlackNotificationType,
    client_id: int,
    base_message: str,
    blocks: list[dict],
    client_sdr_id: Optional[int] = None,
    additional_webhook_urls: Optional[list[WebhookDict]] = [],
    override_webhook_urls: Optional[list[WebhookDict]] = [],
    override_preference: Optional[bool] = False,
    testing: Optional[bool] = False,
) -> bool:
    """Send a Slack message to a list of webhook URLs

    Args:
        notification_type (SlackNotificationType): The type of the notification that is being sent.
        client_id (int): The ID of the Client that the notification is being sent for. SlackBot uses this to get the Client's notification channel.
        base_message (str): The 'base' message that is being sent. This is overriden by blocks.
        blocks (list[dict]): The blocks that are being sent.
        client_sdr_id (Optional[int], optional): The ID of the ClientSDR that this notification pertains to. Defaults to None.
        additional_webhook_urls (Optional[list[dict]], optional): Additional webhook URLs to send the message to. Defaults to [].
        override_webhook_urls (Optional[list[dict]], optional): Webhook URLs to override the Client's webhook URL and additional webhook URLs. Defaults to [].
        override_preference (Optional[bool], optional): Whether or not to override the SDR's notification preference. Defaults to False.
        testing (Optional[bool], optional): Whether or not to send the message to the testing channel. Defaults to False.

    Example call:
        send_slack_message(
            notification_type=SlackNotificationType.AI_REPLY_TO_EMAIL,
            client_id=1,
            base_message="This is a test message",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "This is a test message"
                    }
                }
            ],
            client_sdr_id=1,
            additional_webhook_urls=[
                {
                    "url": "https://hooks.slack.com/services/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",
                    "channel": "slack-notification-testing"
                }
            ],
            override_webhook_urls=[],
            override_preference = True,
            testing=True
        )

    Returns:
        bool: Whether or not the message was successfully sent
    """
    # Ensure that the SDR is subscribed to the notification type
    if client_sdr_id and not override_preference:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        if not client_sdr.is_subscribed_to_slack_notification(notification_type):
            return False

    # Get the Client and the Slack channel that we're sending to
    client: Client = Client.query.get(client_id)
    slack_auth: SlackAuthentication = SlackAuthentication.query.filter_by(
        client_id=client_id
    ).first()
    slack_channel: Union[
        SlackConnectedChannel, None
    ] = SlackConnectedChannel.query.filter_by(client_id=client_id).first()

    # If we're in testing or development, only send to the testing channel
    if (
        os.environ.get("FLASK_ENV") == "testing"
        or os.environ.get("FLASK_ENV") == "development"
        or testing
    ):
        override_webhook_urls = [
            {
                "url": NOTIFICATION_TESTING_CHANNEL,
                "channel": "slack-notification-testing",
            }
        ]
        slack_channel = None

    # Sending Stage 1: Send using the channel token
    if slack_auth and slack_channel:
        result = slack_app.client.chat_postMessage(
            token=slack_auth.slack_access_token,
            channel=slack_channel.slack_channel_id,
            text=base_message,
            blocks=blocks,
        )
        ok = result.get("ok")
        error = None
        if ok:
            # If the message was sent successfully, then update the client's last_slack_msg_date (if applicable)
            client.last_slack_msg_date = datetime.now()
            db.session.commit()
        else:
            error = result.get("error")

        try:
            create_sent_slack_notification_entry(
                notification_type=notification_type,
                message=base_message,
                slack_channel_id=slack_channel.slack_channel_id,
                blocks=blocks,
                client_sdr_id=client_sdr_id,
                error=error,
            )
        except Exception as e:
            send_slack_error_message(type=notification_type, error=str(e))

    # Sending Stage 2: Send using webhook_urls
    webhook_urls: list[WebhookDict] = [
        {
            "url": client.pipeline_notifications_webhook_url,
            "channel": f"{client.company}'s Pipeline Notifications Channel",
        }
    ]
    webhook_urls.extend(additional_webhook_urls) if additional_webhook_urls else None
    if override_webhook_urls:
        webhook_urls = override_webhook_urls

    for webhook_url in webhook_urls:
        if webhook_url is None:
            continue

        url = webhook_url.get("url")
        if url is None or len(url) < 10:
            continue

        # Send the message
        webhook = WebhookClient(url)
        response = webhook.send(text=base_message, blocks=blocks)

        # If there was an error, log it and send a notification, otherwise update the client's last_slack_msg_date (if applicable)
        error = None
        if response.status_code != 200:
            error = f"{response.status_code} - {response.body}"
            send_slack_error_message(type=notification_type.value, error=error)
        else:
            client.last_slack_msg_date = datetime.now()
            db.session.commit()

        try:
            create_sent_slack_notification_entry(
                notification_type=notification_type,
                message=base_message,
                webhook_url=webhook_url,
                blocks=blocks,
                client_sdr_id=client_sdr_id,
                error=error,
            )
        except Exception as e:
            send_slack_error_message(type=notification_type, error=str(e))

    return True


def send_slack_error_message(
    type: str,
    error: str,
) -> None:
    """Send a Slack message to the error channel documenting an error that occurred with a Slack notification

    Args:
        type (str): The type of the notification that errored.
        error (str): The error that occurred.

    Raises:
        Exception: If there was an error sending the Slack message.
    """
    # Send the message
    webhook = WebhookClient(SLACK_ERROR_CHANNEL)
    response = webhook.send(
        text="Error occurred in `" + type + "`:\n```" + error + "```",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Error occurred in `" + type + "`*:\n```" + error + "```",
                },
            },
        ],
    )

    # If there was an error, then we need to Raise an Exception
    if response.status_code != 200:
        raise Exception("Error sending Slack message")

    return


def create_sent_slack_notification_entry(
    notification_type: SlackNotificationType,
    message: str,
    webhook_url: Optional[WebhookDict] = None,
    slack_channel_id: Optional[str] = None,
    blocks: Optional[list[dict]] = [],
    client_sdr_id: Optional[int] = None,
    error: Optional[str] = None,
) -> int:
    """Creates a SentSlackNotification entry in the database

    Args:
        notification_type (SlackNotificationType): Type of Slack notification that was sent
        message (str): The 'base' message that was sent
        webhook_url (WebhookDict): The webhook URL that was sent to
        slack_channel_id (Optional[str], optional): The Slack channel ID that the message was sent to. Defaults to None.
        blocks (Optional[list[dict]], optional): The blocks that were sent. Defaults to [].
        client_sdr_id (Optional[int], optional): The ID of the ClientSDR that sent the notification. Defaults to None.
        error (Optional[str], optional): The error that occurred, if any. Defaults to None.

    Returns:
        int: The ID of the SentSlackNotification entry that was created
    """
    from src.slack.models import SentSlackNotification

    sent_slack_notification = SentSlackNotification(
        client_sdr_id=client_sdr_id,
        notification_type=notification_type,
        message=message,
        webhook_url=webhook_url,
        slack_channel_id=slack_channel_id,
        blocks=blocks,
        error=error,
    )
    db.session.add(sent_slack_notification)
    db.session.commit()

    return sent_slack_notification.id


def subscribe_all_sdrs_to_notification(
    notification_type: SlackNotificationType,
) -> bool:
    """Subscribe all of the SDRs to a Slack notification type

    Args:
        notification_type (SlackNotificationType): The type of the notification that the SDRs are being subscribed to

    Returns:
        bool: Whether or not the SDRs were successfully subscribed to the Slack notification
    """

    from src.client.models import ClientSDR
    from src.subscriptions.services import subscribe_to_slack_notification
    from src.slack.models import SlackNotification

    # Get the ID of this notification type
    slack_notification: SlackNotification = SlackNotification.query.filter_by(
        notification_type=notification_type
    ).first()
    if not slack_notification:
        raise Exception(
            f"Slack notification of type: {notification_type.value} not found"
        )

    # Get all of the active SDRs
    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(active=True).all()

    # Create subscriptions to this notification type for all of the SDRs
    for client_sdr in client_sdrs:
        subscribe_to_slack_notification(
            client_sdr_id=client_sdr.id,
            slack_notification_id=slack_notification.id,
            new_notification=True,
        )

    return True


def subscribe_sdr_to_all_notifications(client_sdr_id: int) -> bool:
    """Subscribe an SDR to all of the Slack notifications

    Args:
        client_sdr_id (int): The ID of the ClientSDR that is being subscribed to all of the Slack notifications

    Returns:
        bool: Whether or not the SDR was successfully subscribed to all of the Slack notifications
    """
    from src.subscriptions.services import subscribe_to_slack_notification
    from src.slack.models import SlackNotification

    # Get all of the active Slack notifications
    slack_notifications: list[SlackNotification] = SlackNotification.query.all()

    # Create subscriptions to all of the Slack notifications for the SDR
    for slack_notification in slack_notifications:
        subscribe_to_slack_notification(
            client_sdr_id=client_sdr_id,
            slack_notification_id=slack_notification.id,
            new_notification=True,
        )

    return True


def unsubscribe_all_sdrs_from_notification(
    notification_type: SlackNotificationType,
) -> bool:
    """Unsubscribe all of the SDRs from a Slack notification type

    Args:
        notification_type (SlackNotificationType): The type of the notification that the SDRs are being unsubscribed from

    Returns:
        bool: Whether or not the SDRs were successfully unsubscribed from the Slack notification
    """
    from src.client.models import ClientSDR
    from src.slack.models import SlackNotification

    # Get the ID of this notification type
    slack_notification: SlackNotification = SlackNotification.query.filter_by(
        notification_type=notification_type
    ).first()
    if not slack_notification:
        raise Exception(
            f"Slack notification of type: {notification_type.value} not found"
        )

    # Get all of the subscriptions to this notification type
    subscriptions: list[Subscription] = Subscription.query.filter_by(
        slack_notification_id=slack_notification.id
    ).all()
    for subscription in subscriptions:
        subscription.active = False
        subscription.deactivation_date = datetime.now()

    db.session.commit()

    return True
