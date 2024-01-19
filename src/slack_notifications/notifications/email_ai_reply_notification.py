from typing import Optional
from src.client.models import Client, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.prospecting.models import Prospect
from src.slack_notifications.models import SlackNotificationType
from src.slack_notifications.slack import send_slack_message


def email_ai_reply_notification(
    prospect_id: int,
    prospect_message: str,
    ai_response: str,
    testing: Optional[bool] = False,
) -> bool:
    """Sends a notification for Email AI Message Sent

    Args:
        prospect_id (int): ID of the Prospect
        prospect_message (str): Message that the Prospect sent
        ai_response (str): Response that the AI sent

    Returns:
        bool: Whether or not the message was successfully sent
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    webhook_urls = [
        {
            "url": client.pipeline_notifications_webhook_url,
            "channel": f"{client.company}'s Pipeline Notifications Channel",
        }
    ]

    outreach_status: str = (
        prospect_email.outreach_status.value
        if prospect_email.outreach_status
        else "UNKNOWN"
    )
    outreach_status = outreach_status.split("_")
    outreach_status = " ".join(word.capitalize() for word in outreach_status)
    direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
        auth_token=client_sdr.auth_token,
        prospect_id=prospect_id if prospect_id else "",
    )

    send_slack_message(
        notification_type=SlackNotificationType.AI_REPLY_TO_EMAIL,
        message="SellScale AI just replied to prospect on Email!",
        webhook_urls=webhook_urls,
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💬 SellScale AI just replied to "
                    + prospect.full_name
                    + " on Email",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Convo Status: `{outreach_status}`",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*{prospect_first_name}*:\n>{prospect_message}\n\n*{first_name} (AI)*:\n>{ai_response}".format(
                        prospect_first_name=prospect.first_name,
                        prospect_message=prospect_message[:150],
                        ai_response=ai_response[:400] + "..."
                        if len(ai_response) > 400
                        else ai_response,
                        first_name=client_sdr.name.split(" ")[0],
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "🧳 Title: "
                        + str(prospect.title)
                        + " @ "
                        + str(prospect.company)[0:20]
                        + ("..." if len(prospect.company) > 20 else ""),
                        "emoji": True,
                    },
                    {
                        "type": "plain_text",
                        "text": "📌 SDR: " + client_sdr.name,
                        "emoji": True,
                    },
                ],
            },
            {
                "type": "section",
                "block_id": "sectionBlockWithLinkButton",
                "text": {"type": "mrkdwn", "text": "View Conversation in Sight"},
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Convo",
                        "emoji": True,
                    },
                    "value": direct_link,
                    "url": direct_link,
                    "action_id": "button-action",
                },
            },
        ],
        client_sdr_id=client_sdr.id,
        testing=testing,
    )

    return True
