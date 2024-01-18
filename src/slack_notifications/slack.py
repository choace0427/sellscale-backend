# How to use Slack Notification blocks: https://api.slack.com/reference/block-kit/blocks
# How to add a Webhook: https://api.slack.com/messaging/webhooks

import os

from app import db
from typing import Optional
from slack_sdk.webhook import WebhookClient
from datetime import datetime

from model_import import Client


####################################
# REGISTER NOTIFICATION TYPES HERE #
####################################
# Define what notifications types call what functions
# - function must return a boolean for success or failure
# - args are passed into the function from meta_data.args
NOTIFICATION_TYPE_MAP = {""}


NOTIFICATION_TESTING_CHANNEL = (
    "https://hooks.slack.com/services/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"
)
SLACK_ERROR_CHANNEL = (
    "https://hooks.slack.com/services/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"
)


def send_slack_message(
    type: str,
    message: str,
    webhook_urls: list[dict],
    blocks: Optional[list[dict]] = [],
    client_sdr_id: Optional[int] = None,
    testing: Optional[bool] = False,
) -> bool:
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
            send_slack_error_message(type=type, error=error)
        else:
            clients: list[Client] = Client.query.filter(
                Client.pipeline_notifications_webhook_url.like(f"%{url}%")
            ).all()
            for client in clients:
                if client:
                    client.last_slack_msg_date = datetime.now()
                    db.session.commit()

        create_sent_slack_notification_entry(
            type=type,
            message=message,
            webhook_url=webhook_url,
            blocks=blocks,
            client_sdr_id=client_sdr_id,
            error=error,
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
    type: str,
    message: str,
    webhook_url: dict,
    blocks: Optional[list[dict]] = [],
    client_sdr_id: Optional[int] = None,
    error: Optional[str] = None,
) -> int:
    from src.slack_notifications.models import SentSlackNotification

    sent_slack_notification = SentSlackNotification(
        client_sdr_id=client_sdr_id,
        type=type,
        message=message,
        webhook_url=webhook_url,
        blocks=blocks,
        error=error,
    )
    db.session.add(sent_slack_notification)
    db.session.commit()

    return sent_slack_notification.id
