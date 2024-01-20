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

from app import db
from typing import Optional
from slack_sdk.webhook import WebhookClient
from datetime import datetime

from model_import import Client
from src.client.models import ClientSDR
from src.slack_notifications.models import SlackNotificationType


NOTIFICATION_TESTING_CHANNEL = (
    "https://hooks.slack.com/services/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"
)
SLACK_ERROR_CHANNEL = (
    "https://hooks.slack.com/services/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"
)


def send_slack_message(
    notification_type: SlackNotificationType,
    message: str,
    webhook_urls: list[dict],
    blocks: Optional[list[dict]] = [],
    client_sdr_id: Optional[int] = None,
    testing: Optional[bool] = False,
) -> bool:
    """Send a Slack message to a list of webhook URLs

    Args:
        notification_type (SlackNotificationType): The type of the notification that is being sent.
        message (str): The 'base' message to send, usually not the full message.
        webhook_urls (list[dict]): A list of webhook URLs to send the message to, see example below.
        blocks (Optional[list[dict]], optional): The message blocks that compose the full message. Defaults to [].
        client_sdr_id (Optional[int], optional): The ID of the ClientSDR, used to identify the sender. Defaults to None, which signifies a 'test' message or a message that does originate from the SDR.
        testing (Optional[bool], optional): Denotes whether to send the message to a testing channel. Defaults to False.

    Example call:
        send_slack_message(
            type="email_ai_message_sent",
            message="SellScale AI just replied to prospect on Email!",
            webhook_urls=[
                {
                    "url": client.pipeline_notifications_webhook_url,
                    "channel": f"{client.company}'s Pipeline Notifications Channel",
                }
            ],
            blocks=[],
            client_sdr_id=client_sdr.id,
            testing=False,
        )

    Returns:
        bool: Whether or not the message was successfully sent
    """
    # Ensure that the SDR is subscribed to the notification type
    if client_sdr_id:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        if not client_sdr.is_subscribed_to_slack_notification(notification_type):
            return False

    # If we're in testing or development, send to the testing channel
    if (
        os.environ.get("FLASK_ENV") == "testing"
        or os.environ.get("FLASK_ENV") == "development"
        or testing
    ):
        webhook_urls = [
            {
                "url": NOTIFICATION_TESTING_CHANNEL,
                "channel": "slack-notification-testing",
            }
        ]

    for webhook_url in webhook_urls:
        if webhook_url is None:
            continue

        url = webhook_url.get("url")
        if url is None or len(url) < 10:
            continue

        # Send the message
        webhook = WebhookClient(url)
        response = webhook.send(text=message, blocks=blocks)

        # If there was an error, log it and send a notification, otherwise update the client's last_slack_msg_date (if applicable)
        error = None
        if response.status_code != 200:
            error = f"{response.status_code} - {response.body}"
            send_slack_error_message(type=notification_type.value, error=error)
        else:
            clients: list[Client] = Client.query.filter(
                Client.pipeline_notifications_webhook_url.like(f"%{url}%")
            ).all()
            for client in clients:
                if client:
                    client.last_slack_msg_date = datetime.now()
                    db.session.commit()

        try:
            create_sent_slack_notification_entry(
                notification_type=notification_type,
                message=message,
                webhook_url=webhook_url,
                blocks=blocks,
                client_sdr_id=client_sdr_id,
                error=error,
            )
        except Exception as e:
            send_slack_error_message(
                type=SlackNotificationType.AI_REPLY_TO_EMAIL.value, error=str(e)
            )

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
    webhook_url: dict,
    blocks: Optional[list[dict]] = [],
    client_sdr_id: Optional[int] = None,
    error: Optional[str] = None,
) -> int:
    """Creates a SentSlackNotification entry in the database

    Args:
        notification_type (SlackNotificationType): Type of Slack notification that was sent
        message (str): The 'base' message that was sent
        webhook_url (dict): The webhook URL that was sent to
        blocks (Optional[list[dict]], optional): The blocks that were sent. Defaults to [].
        client_sdr_id (Optional[int], optional): The ID of the ClientSDR that sent the notification. Defaults to None.
        error (Optional[str], optional): The error that occurred, if any. Defaults to None.

    Returns:
        int: The ID of the SentSlackNotification entry that was created
    """
    from src.slack_notifications.models import SentSlackNotification

    sent_slack_notification = SentSlackNotification(
        client_sdr_id=client_sdr_id,
        notification_type=notification_type,
        message=message,
        webhook_url=webhook_url,
        blocks=blocks,
        error=error,
    )
    db.session.add(sent_slack_notification)
    db.session.commit()

    return sent_slack_notification.id
