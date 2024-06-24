from typing import Optional
from src.client.models import Client, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import WebhookDict, slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class EmailAIReplyNotification(SlackNotificationClass):
    """A Slack notification that is sent when the AI replies to an email

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to
    `prospect_message`: The message that the Prospect sent
    `ai_response`: The response that the AI sent

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "prospect_name",
        "prospect_title",
        "prospect_company",
        "prospect_first_name",
        "outreach_status",
        "direct_link",
        "prospect_message",
        "ai_response",
    }

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

    def send_notification(self, preview_mode: bool) -> bool:
        """Sends a notification to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Args:
            preview_mode (bool): Whether or not the notification is being sent in preview mode. Preview mode sends to a 'dummy' message to the channel.

        Returns:
            bool: Whether or not the message was successfully sent
        """

        def get_preview_fields() -> dict:
            """Gets the fields to be used in the preview message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            return {
                "prospect_name": "John Doe",
                "prospect_title": "CEO",
                "prospect_company": "SomeCompany",
                "prospect_first_name": "John",
                "outreach_status": "Active Convo Question",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token
                ),
                "prospect_message": "Which days can you meet?",
                "ai_response": "I'm free on Monday, Wednesday, and Friday between 2pm and 4pm. What works best for you?",
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            prospect: Prospect = Prospect.query.get(self.prospect_id)
            prospect_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )

            return {
                "prospect_name": prospect.full_name,
                "prospect_title": prospect.title,
                "prospect_company": prospect.company,
                "prospect_first_name": prospect.first_name,
                "outreach_status": (
                    prospect_email.outreach_status.value
                    if prospect_email.outreach_status
                    else "UNKNOWN"
                ),
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=self.prospect_id if self.prospect_id else "",
                ),
                "prospect_message": self.prospect_message,
                "ai_response": self.ai_response,
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Validate
        self.validate_required_fields(fields)

        # Get the fields
        prospect_name = fields.get("prospect_name")
        prospect_title = fields.get("prospect_title")
        prospect_company = fields.get("prospect_company")
        prospect_first_name = fields.get("prospect_first_name")
        outreach_status = fields.get("outreach_status")
        direct_link = fields.get("direct_link")
        prospect_message = fields.get("prospect_message")
        ai_response = fields.get("ai_response")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.AI_REPLY_TO_EMAIL,
            client_id=client.id,
            base_message="💬 SellScale AI just replied to prospect on Email!",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "💬 SellScale AI just replied to "
                        + prospect_name
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
                            prospect_first_name=prospect_first_name,
                            prospect_message=prospect_message[:150],
                            ai_response=(
                                ai_response[:400] + "..."
                                if len(ai_response) > 400
                                else ai_response
                            ),
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
                            + str(prospect_title)
                            + " @ "
                            + str(prospect_company)[0:20]
                            + ("..." if len(prospect_company) > 20 else ""),
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
            override_preference=preview_mode,
            testing=self.developer_mode,
        )

        return True

    def send_notification_preview(self) -> bool:
        """Sends a test notification (using dummy data) to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Returns:
            bool: Whether or not the message was successfully sent
        """
        return super().send_notification_preview()
