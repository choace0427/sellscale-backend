from typing import Optional, Union
from model_import import (
    ProspectStatus,
    ProspectChannels,
    Prospect,
    ProspectEmailOutreachStatus,
    Client,
    ClientSDR,
)
from src.client.models import ClientArchetype
from src.email_outbound.models import ProspectEmail
from src.li_conversation.models import LinkedinConversationEntry
from src.message_generation.models import GeneratedMessage
from src.utils.slack import send_slack_message
from src.utils.slack import URL_MAP


def send_status_change_slack_block(
    outreach_type: ProspectChannels,
    prospect: Prospect,
    new_status: Union[ProspectStatus, ProspectEmailOutreachStatus],
    custom_message: str,
    metadata: dict = None,
    last_email_message: str = None,
    footer_note: Optional[str] = None,
    custom_webhook_urls: list[str] = None,
) -> None:
    """Sends a status change message to the appropriate slack channel

    Args:
        outreach_type (ProspectChannels): Type of outreach
        prospect (Prospect): The prospect which was updated
        new_status (ProspectStatus | ProspectEmailOutreachStatus): The new status
        status_suffix (str): The suffix to add to the title, regarding the status
        metadata (dict, optional): Metadata. Defaults to None.
        last_email_message (str, optional): The last email message. Defaults to None.
        footer_note (str, optional): The footer note. Defaults to None.
        custom_webhook_urls (list[str], optional): Custom webhook urls. Defaults to None.

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
    client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    persona = client_archetype.archetype
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    generated_message: GeneratedMessage = GeneratedMessage.query.filter_by(
        id=prospect.approved_outreach_message_id
    ).first()
    prospect_email: ProspectEmail = ProspectEmail.query.filter_by(
        id=prospect.approved_outreach_message_id
    ).first()

    date_sent = ""
    if outreach_type == ProspectChannels.EMAIL and prospect_email:
        date_sent = prospect_email.created_at.strftime("%m/%d/%Y")
    elif outreach_type == ProspectChannels.LINKEDIN and generated_message:
        date_sent = generated_message.created_at.strftime("%m/%d/%Y")

    # Find available webhook urls
    webhook_urls = [URL_MAP["sellscale_pipeline_all_clients"]]
    if client.pipeline_notifications_webhook_url and (
        (outreach_type == ProspectChannels.LINKEDIN and client.notification_allowlist)
        or (outreach_type == ProspectChannels.EMAIL)
    ):
        webhook_urls.append(client.pipeline_notifications_webhook_url)

    if (
        client_sdr
        and client_sdr.pipeline_notifications_webhook_url
        and (
            (
                outreach_type == ProspectChannels.LINKEDIN
                and client_sdr.notification_allowlist
            )
            or (outreach_type == ProspectChannels.EMAIL)
        )
    ):
        webhook_urls.append(client_sdr.pipeline_notifications_webhook_url)

    # If custom webhook urls are provided, use them instead
    if custom_webhook_urls:
        webhook_urls = custom_webhook_urls

    # Get last messages using URN ID
    has_messages = False
    convo: list[LinkedinConversationEntry] = []
    if outreach_type == ProspectChannels.LINKEDIN:
        urn_id = prospect.li_conversation_urn_id
        convo: list[LinkedinConversationEntry] = (
            LinkedinConversationEntry.query.filter_by(
                conversation_url=f"https://www.linkedin.com/messaging/thread/{urn_id}/"
            )
            .order_by(LinkedinConversationEntry.created_at.desc())
            .limit(5)
            .all()
        )
        if len(convo) > 0:
            has_messages = True

    # Craft message
    message_blocks = []
    message_blocks.append(
        {  # Add header
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": prospect.full_name + "#" + str(prospect.id) + custom_message,
                "emoji": True,
            },
        }
    )

    message_blocks.append(
        {  # Add persona
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Persona:* {persona}".format(
                    persona=persona if persona else "-"
                ),
            },
        }
    )

    email_address = metadata.get("prospect_email") if metadata else None
    message_blocks.append(
        {  # Add prospect title and (optional) last message
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Title:* {title}\n*Company:* {company}{last_message}{email_address}".format(
                    title=prospect.title,
                    company=prospect.company,
                    last_message="\n*Last message:* {}...".format(last_email_message)
                    if last_email_message
                    else "",
                    email_address="\n*Prospect Email:* {}".format(email_address)
                    if email_address
                    else "",
                ),
            },
        }
    )

    # If email, include email information
    if outreach_type == ProspectChannels.EMAIL:
        subject = metadata.get("email_title") if metadata else None
        email_snippet = metadata.get("email_snippet") if metadata else None
        prospect_message = metadata.get("prospect_message") if metadata else None

        if subject:
            message_blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Email Subject*:\n>{subject}"},
                },
            )
        if email_snippet:
            message_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Sent Email*:\n>{email_snippet}",
                    },
                },
            )
        if prospect_message:
            # We need to make sure that newlines aren't escaping the > (quote) in the slack message
            prospect_message = prospect_message.replace("\n", "\n>")
            message_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Prospect Reply*:\n>{prospect_message}",
                    },
                },
            )

    # If we have messages, send them
    if has_messages:
        for c in reversed(convo):
            if c.connection_degree == "You":
                message_blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*{sender}:* {message}".format(
                                sender=c.author, message=c.message
                            ),
                        },
                    }
                )
            else:
                message_blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*{sender}:* {message}".format(
                                sender=c.author,
                                degree=c.connection_degree,
                                message=c.message,
                            ),
                        },
                    }
                )

    if footer_note:
        message_blocks.append(
            {  # Add footer note
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": footer_note,
                        "emoji": True,
                    }
                ],
            }
        )

    channel_text = "Email" if outreach_type == ProspectChannels.EMAIL else "LinkedIn"
    message_blocks.append(
        {  # Add SDR information
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
                    "text": "📆 Initial Send: {}".format(date_sent),
                    "emoji": True,
                },
                {
                    "type": "plain_text",
                    "text": "📤 Outbound channel: {}".format(channel_text),
                    "emoji": True,
                },
            ],
        }
    )

    # if icp fit reason exists and next status is not accepted
    if prospect.icp_fit_reason and new_status == ProspectStatus.DEMO_SET:
        message_blocks.append(
            {  # Add ICP fit reason
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*ICP fit reason:* {}".format(prospect.icp_fit_reason),
                },
            }
        )

    if outreach_type == ProspectChannels.LINKEDIN:  # Add next steps for Linkedin
        sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
        direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=all/contacts/{prospect_id}".format(
            auth_token=sdr.auth_token,
            prospect_id=prospect.id,
        )

        message_blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": " ",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Convo in Sight",
                        "emoji": True,
                    },
                    "value": direct_link,
                    "url": direct_link,
                    "action_id": "button-action",
                },
            }
        )
    elif outreach_type == ProspectChannels.EMAIL:  # Add next steps for Email
        message_blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Next steps: Respond through your email client",
                },
            }
        )

    message_blocks.append(
        {  # Add divider
            "type": "divider",
        }
    )

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
    client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    persona = client_archetype.archetype
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
                    "text": "*Persona:* {persona}\n".format(
                        persona=persona if persona else "-"
                    ),
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
                    "text": " ",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Convo in Sight",
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
