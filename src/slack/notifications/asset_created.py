import datetime
from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.ai_requests.models import AIRequest
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class AssetCreatedNotification(SlackNotificationClass):
    """A Slack notification that is sent whenever the SDR gives feedback on a Demo

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.

    This class inherits from SlackNotificationClass.
    """

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        asset_name: Optional[str] = None,
        asset_tags: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.asset_name = asset_name
        self.asset_tags = asset_tags

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
                "asset_name": "Fortune 500 Case Study",
                "asset_tags": "Case Study | Fortune 500",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=analytics".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            return {
                "asset_name": self.asset_name,
                "asset_tags": (
                    " | ".join(self.asset_tags)
                    if (self.asset_tags and len(self.asset_tags) > 0)
                    else "_No tags_"
                ),
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=analytics".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        asset_name = fields.get("asset_name")
        asset_tags = fields.get("asset_tags")
        direct_link = fields.get("direct_link")
        if not asset_name or not asset_tags or not direct_link:
            return False

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.ASSET_CREATED,
            client_id=client.id,
            base_message=f"🧠 New Asset ingested",
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🧠 New Asset ingested"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Your SellScale outreach just got smarter from a new asset.",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"📄 Name: {asset_name}"},
                        {"type": "mrkdwn", "text": f"🔎 Tags: {asset_tags}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": " "},
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in Asset Library →",
                            "emoji": True,
                        },
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
