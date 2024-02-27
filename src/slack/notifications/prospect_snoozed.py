from datetime import datetime, timedelta
from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class ProspectSnoozedNotification(SlackNotificationClass):
    """A Slack notification that is sent whenever the SDR gives feedback on a Demo

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
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
        hidden_until: Optional[str] = None,
        outbound_channel: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.prospect_message = prospect_message
        self.ai_response = ai_response
        self.hidden_until = hidden_until
        self.outbound_channel = outbound_channel

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

            couple_of_weeks = datetime.now() + timedelta(weeks=2)

            return {
                "archetype_name": "CEOs at AI Companies",
                "archetype_emoji": "🤖",
                "prospect_name": "John Doe",
                "prospect_message": "Hey maybe circle back with me in a couple of weeks.",
                "ai_response": "No problem at all, John. I'll touch base with you in a couple of weeks. In the meantime, if you have any questions or need any information, feel free to reach out.",
                "hidden_until": couple_of_weeks.strftime("%B %d, %Y"),
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=contacts/".format(
                    auth_token=client_sdr.auth_token,
                ),
                "outbound_channel": "LinkedIn",
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            prospect: Prospect = Prospect.query.get(self.prospect_id)
            archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )

            return {
                "archetype_name": archetype.archetype,
                "archetype_emoji": archetype.emoji,
                "prospect_name": prospect.full_name,
                "prospect_message": self.prospect_message,
                "ai_response": self.ai_response,
                "hidden_until": self.hidden_until,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=prospect.id,
                ),
                "outbound_channel": self.outbound_channel,
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        archetype_name = fields.get("archetype_name")
        archetype_emoji = fields.get("archetype_emoji")
        prospect_name = fields.get("prospect_name")
        prospect_message = fields.get("prospect_message")
        ai_response = fields.get("ai_response")
        hidden_until = fields.get("hidden_until")
        direct_link = fields.get("direct_link")
        outbound_channel = fields.get("outbound_channel")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.PROSPECT_SNOOZED,
            client_id=client.id,
            base_message=f"⏰ SellScale AI just snoozed a prospect",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⏰ SellScale AI just snoozed "
                        + prospect_name
                        + " to "
                        + hidden_until
                        + ".",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*Last Message from Prospect:* _{prospect_message}_\n\n*AI Response:* _{ai_response}_"
                        ).format(
                            prospect_message=(
                                prospect_message.replace("\n", " ")
                                if prospect_message
                                else "-"
                            ),
                            ai_response=(
                                ai_response.replace("\n", " ") if ai_response else "-"
                            ),
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "😎 Contact: {sdr}".format(
                                sdr=client_sdr.name,
                            ),
                            "emoji": True,
                        },
                        {
                            "type": "plain_text",
                            "text": "👤 Campaign: {emoji} {persona}".format(
                                persona=archetype_name if archetype_name else "-",
                                emoji=archetype_emoji,
                            ),
                        },
                        {
                            "type": "plain_text",
                            "text": f"📤 Outbound channel: {outbound_channel}",
                            "emoji": True,
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Message will re-appear in SellScale inbox on "
                        + hidden_until
                        + ".",
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
