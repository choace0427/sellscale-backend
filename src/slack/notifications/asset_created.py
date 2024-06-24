import datetime
from typing import Optional

from bs4 import BeautifulSoup
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

    required_fields = {
        "asset_name",
        "asset_type",
        "ai_summary",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        client_archetype_ids: Optional[list[int]] = None,
        asset_name: Optional[str] = None,
        asset_type: Optional[str] = None,
        ai_summary: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.client_archetype_ids = client_archetype_ids
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.ai_summary = ai_summary

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
                "client_archetype_names": "CEOs of AI Companies",
                "asset_name": "Fortune 500 Case Study",
                "asset_type": "Case Study | Fortune 500",
                "ai_summary": "A Fortune 500 company greatly benefited by using this product. They saw an increase in all valuable metrics by over 50%. The CEO of the company was very pleased and has provided a testimonial.",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=analytics".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            # Get the campaign names
            client_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
                ClientArchetype.id.in_(self.client_archetype_ids)
            ).all()
            client_archetype_names = []
            for archetype in client_archetypes:
                client_archetype_names.append(archetype.archetype)

            # Get the formatted AI summary
            spaced_text = self.ai_summary.replace(
                "</p>", "</p> "
            )  # We add a space in between HTML tags in the ai_summary in case there are Links
            bs = BeautifulSoup(
                spaced_text, "html.parser"
            )  # We run the spaced text through beautiful soup. Non-HTML will be okay.
            formatted_ai_summary = (
                bs.get_text()
            )  # We strip the HTML tags by getting the raw text
            formatted_ai_summary = (
                formatted_ai_summary.strip()
            )  # Get rid of any spaces at the beginning or end

            return {
                "client_archetype_names": ", ".join(client_archetype_names)
                or "_No campaign attached_",
                "asset_name": self.asset_name,
                "asset_type": (
                    " | ".join(self.asset_type)
                    if (self.asset_type and len(self.asset_type) > 0)
                    else "_No tags_"
                ),
                "ai_summary": formatted_ai_summary,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=analytics".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Validate
        self.validate_required_fields(fields)

        # Get the fields
        client_archetype_names = fields.get("client_archetype_names")
        asset_name = fields.get("asset_name")
        asset_type = fields.get("asset_type")
        ai_summary = fields.get("ai_summary")
        direct_link = fields.get("direct_link")

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
                        "text": "📙 *Name*: _{asset_name}_\n*👤 Campaign(s)*: {campaign_names}\n*🏷️ Asset Type*: {asset_type}\n*AI Summary*:\n {ai_summary}".format(
                            asset_name=asset_name,
                            campaign_names=client_archetype_names,
                            asset_type=asset_type,
                            ai_summary=ai_summary,
                        ),
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "SellScale ingested a new asset to be used in outreach.",
                        },
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
