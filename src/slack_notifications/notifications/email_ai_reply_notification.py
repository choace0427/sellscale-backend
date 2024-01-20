from typing import Optional
from src.client.models import Client, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.prospecting.models import Prospect
from src.slack_notifications.models import SlackNotificationType
from src.slack_notifications.slack import send_slack_message
from src.slack_notifications.slack_notification import SlackNotificationClass


class EmailAIReplyNotification(SlackNotificationClass):
    """A Slack notification that is sent when the AI replies to an email

    `client_sdr_id`: The ID of the ClientSDR that sent the notification
    `developer_mode`: Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to
    `prospect_message`: The message that the Prospect sent
    `ai_response`: The response that the AI sent

    This class inherits from SlackNotificationClass.
    """

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        prospect_message: Optional[str] = None,
        ai_response: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.prospect_message = prospect_message
        self.ai_response = ai_response

        return

    def send_notification(self) -> bool:
        """Sends a notification to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Returns:
            bool: Whether or not the message was successfully sent
        """
        # Can't send a notification if we don't have the required attributes
        if not self.prospect_id or not self.prospect_message or not self.ai_response:
            return False

        prospect: Prospect = Prospect.query.get(self.prospect_id)

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
            prospect_id=self.prospect_id if self.prospect_id else "",
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
                            prospect_message=self.prospect_message[:150],
                            ai_response=self.ai_response[:400] + "..."
                            if len(self.ai_response) > 400
                            else self.ai_response,
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
            testing=self.developer_mode,
        )

        return True

    def send_test_notification(self) -> bool:
        """Sends a test notification (using dummy data) to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Returns:
            bool: Whether or not the message was successfully sent
        """
        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        webhook_urls = [
            {
                "url": client.pipeline_notifications_webhook_url,
                "channel": f"{client.company}'s Pipeline Notifications Channel",
            }
        ]

        direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
            auth_token=client_sdr.auth_token,
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
                        "text": "💬 SellScale AI just replied to John Doe on Email",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Convo Status: `Active Convo Question`",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*{prospect_first_name}*:\n>{prospect_message}\n\n*{first_name} (AI)*:\n>{ai_response}".format(
                            prospect_first_name="John Doe",
                            prospect_message="Which days can you meet?",
                            ai_response="I'm free on Monday, Wednesday, and Friday between 2pm and 4pm. What works best for you?",
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
                            "text": "🧳 Title: CEO @ SomeCompany",
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
            testing=self.developer_mode,
            override_preference=True,
        )

        return True
