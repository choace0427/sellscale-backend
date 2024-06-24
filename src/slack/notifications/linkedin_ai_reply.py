from typing import Optional
from src.client.models import Client, ClientSDR
from src.prospecting.models import Prospect
from src.bump_framework.models import BumpFramework
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class LinkedInAIReplyNotification(SlackNotificationClass):
    """A Slack notification that is sent when the Prospect accepts a LinkedIn invite

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to
    `prospect_message`: The message that the Prospect sent
    `ai_response`: The response that the AI sent
    `bump_framework_id`: The ID of the Bump Framework

    This class inherits from SlackNotificationClass.
    """

    required_fields = {"prospect_name", "prospect_title", "prospect_company", "prospect_message", "prospect_status", "ai_response", "direct_link"}

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        bump_framework_id: Optional[int] = None,
        status: Optional[str] = None,
        ai_response: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.bump_framework_id = bump_framework_id
        self.status = status
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
                "prospect_message": "Hi, happy to connect!",
                "prospect_status": "Active Convo Revival",
                "ai_response": "Just checking in, John. Were you able to find a suitable time for our chat? I'm eager to connect and hear your insights.",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            prospect: Prospect = Prospect.query.get(self.prospect_id)

            return {
                "prospect_name": prospect.full_name,
                "prospect_title": prospect.title,
                "prospect_company": prospect.company,
                "prospect_message": prospect.li_last_message_from_prospect,
                "prospect_status": self.status,
                "ai_response": self.ai_response,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=prospect.id,
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        prospect_name = fields.get("prospect_name")
        prospect_title = fields.get("prospect_title", "-")
        prospect_company = fields.get("prospect_company", "-")
        prospect_message = fields.get("prospect_message", "-")
        prospect_status = fields.get("prospect_status", "-")
        ai_response = fields.get("ai_response", "-")
        direct_link = fields.get("direct_link")

        #validate required fields
        self.validate_required_fields(fields)

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        bump_framework_title = "Smart Generate"
        if self.bump_framework_id:
            bump_framework: BumpFramework = BumpFramework.query.get(
                self.bump_framework_id
            )
            if bump_framework:
                bump_framework_title = bump_framework.title

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.LINKEDIN_AI_REPLY,
            client_id=client.id,
            base_message=f"💬 SellScale AI just replied to prospect!",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"💬 SellScale AI just replied to {prospect_name}",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Convo Status: `{prospect_status}`",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*✨ AI Reply Framework:* `{bump_framework_title}`",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*{prospect_name}*:\n>{prospect_message}\n\n*{sdr_name} (AI)*:\n>{ai_response}".format(
                            prospect_name=prospect_name,
                            prospect_message=(prospect_message.replace("\n", " ")),
                            sdr_name=client_sdr.name,
                            ai_response=ai_response.replace("\n", " "),
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
