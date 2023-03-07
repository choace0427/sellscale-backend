from typing import Union
from model_import import ProspectStatus, ProspectChannels, Prospect, ProspectEmailOutreachStatus, Client, ClientSDR
from src.utils.slack import send_slack_message
from src.utils.slack import URL_MAP


def send_status_change_slack_block(
    outreach_type: ProspectChannels,
    prospect: Prospect,
    new_status: Union[ProspectStatus, ProspectEmailOutreachStatus],
    custom_message: str,
    metadata: dict = None,
) -> None:
    """ Sends a status change message to the appropriate slack channel

    Args:
        outreach_type (ProspectChannels): Type of outreach
        prospect (Prospect): The prospect which was updated
        new_status (ProspectStatus | ProspectEmailOutreachStatus): The new status
        status_suffix (str): The suffix to add to the title, regarding the status
        metadata (dict, optional): Metadata. Defaults to None.

    Raises:
        ValueError: Raise a ValueError if the status doesn't belong to the outreach type
    """
    if outreach_type == ProspectChannels.LINKEDIN:
        if new_status not in ProspectStatus.all_statuses():
            raise ValueError("Invalid status")
    elif outreach_type == ProspectChannels.EMAIL:
        if new_status not in ProspectEmailOutreachStatus.all_statuses():
            raise ValueError("Invalid status")

    client: Client = Client.query.get(prospect.client_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    # Find available webhook urls
    webhook_urls = [URL_MAP["sellscale_pipeline_all_clients"]]
    if (
        client.pipeline_notifications_webhook_url
        and client.notification_allowlist
        and new_status in client.notification_allowlist
    ):
        webhook_urls.append(client.pipeline_notifications_webhook_url)
    if (
        client_sdr
        and client_sdr.pipeline_notifications_webhook_url
        and client_sdr.notification_allowlist
        and new_status in client_sdr.notification_allowlist
    ):
        webhook_urls.append(client_sdr.pipeline_notifications_webhook_url)

    # Get last message
    if outreach_type == ProspectChannels.LINKEDIN:
        last_message_from_prospect = prospect.li_last_message_from_prospect
    else:
        last_message_from_prospect = None

    # Craft message
    message_blocks = []
    message_blocks.append({     # Add header
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": prospect.full_name
            + "#"
            + str(prospect.id)
            + custom_message,
            "emoji": True,
        },
    })
    message_blocks.append({     # Add prospect title and (optional) last message
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Title:* {title}\n{last_message}".format(
                title=prospect.title,
                last_message=""
                if not last_message_from_prospect
                else '*Last Message*: "{}"'.format(
                    last_message_from_prospect
                ),
            ),
        },
    })
    channel_text = "Email" if outreach_type == ProspectChannels.EMAIL else "LinkedIn"
    message_blocks.append({    # Add SDR information
        "type": "context",
        "elements": [
            {
                "type": "plain_text",
                "text": "😎 Contact: {}".format(
                    client_sdr.name if client_sdr else "NOT FOUND"
                ),
                "emoji": True,
            },
            {
                "type": "plain_text",
                "text": "🧳 Representing: {}".format(client.company),
                "emoji": True,
            },
            {
                "type": "plain_text",
                "text": "📤 Outbound channel: {}".format(channel_text),
                "emoji": True,
            },
        ],
    })

    if outreach_type == ProspectChannels.LINKEDIN: # Add next steps for Linkedin
        message_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Next steps: Respond on Linkedin conversation thread",
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Click to see Linkedin Thread",
                    "emoji": True,
                },
                "value":  metadata.get("threadUrl")
                or "https://www.linkedin.com",
                "url": metadata.get("threadUrl")
                or "https://www.linkedin.com",
                "action_id": "button-action",
            },
        })
    elif outreach_type == ProspectChannels.EMAIL: # Add next steps for Email
        message_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Next steps: Respond through your email client",
            },
        })

    message_blocks.append({    # Add divider
        "type": "divider",
    })

    send_slack_message(
        message=prospect.full_name + custom_message,
        blocks=message_blocks,
        webhook_urls=webhook_urls,
    )

    return

# Deprecated
def send_slack_block(
    message_suffix: str,
    prospect: Prospect,
    li_message_payload: any,
    new_status: ProspectStatus = None,
):
    client: Client = Client.query.get(prospect.client_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    li_last_message_from_prospect = prospect.li_last_message_from_prospect

    webhook_urls = [URL_MAP["sellscale_pipeline_all_clients"]]
    if (
        client.pipeline_notifications_webhook_url
        and client.notification_allowlist
        and new_status in client.notification_allowlist
    ):
        webhook_urls.append(client.pipeline_notifications_webhook_url)
    if (
        client_sdr
        and client_sdr.pipeline_notifications_webhook_url
        and client_sdr.notification_allowlist
        and new_status in client_sdr.notification_allowlist
    ):
        webhook_urls.append(client_sdr.pipeline_notifications_webhook_url)

    send_slack_message(
        message=prospect.full_name + message_suffix,
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": prospect.full_name
                    + "#"
                    + str(prospect.id)
                    + message_suffix,
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Title:* {title}\n{last_message}".format(
                        title=prospect.title,
                        last_message=""
                        if not li_last_message_from_prospect
                        else '*Last Message*: "{}"'.format(
                            li_last_message_from_prospect
                        ),
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "😎 Contact: {}".format(
                            client_sdr.name if client_sdr else "NOT FOUND"
                        ),
                        "emoji": True,
                    },
                    {
                        "type": "plain_text",
                        "text": "🧳 Representing: {}".format(client.company),
                        "emoji": True,
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Next steps: Respond on Linkedin conversation thread",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Click to see Linkedin Thread",
                        "emoji": True,
                    },
                    "value": li_message_payload.get("threadUrl")
                    or "https://www.linkedin.com",
                    "url": li_message_payload.get("threadUrl")
                    or "https://www.linkedin.com",
                    "action_id": "button-action",
                },
            },
            {"type": "divider"},
        ],
        webhook_urls=webhook_urls,
    )
