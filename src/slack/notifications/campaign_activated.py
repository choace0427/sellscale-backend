from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import WebhookDict, slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class CampaignActivatedNotification(SlackNotificationClass):
    """A Slack notification that is sent when the user clicks on a link in an email

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "sequence_name",
        "example_prospect_name",
        "example_prospect_title",
        "example_prospect_company",
        "example_prospect_linkedin_url",
        "example_message",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        campaign_id: Optional[int] = None,
        example_prospect_name: Optional[str] = None,
        example_prospect_title: Optional[str] = None,
        example_prospect_company: Optional[str] = None,
        example_prospect_linkedin_url: Optional[str] = None,
        example_message: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.campaign_id = campaign_id
        self.example_prospect_name = example_prospect_name
        self.example_prospect_title = example_prospect_title
        self.example_prospect_company = example_prospect_company
        self.example_prospect_linkedin_url = example_prospect_linkedin_url
        self.example_message = example_message

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
                "sequence_name": "CEOs at AI Companies",
                "example_prospect_name": "John Doe",
                "example_prospect_title": "CEO",
                "example_prospect_company": "SomeCompany",
                "example_prospect_linkedin_url": client_sdr.linkedin_url
                or "linkedin.com",
                "example_message": "Hey John, I saw your post on LinkedIn and wanted to reach out. I'm a big fan of your work and would love to connect. Let me know if you're open to it. Thanks!",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            client_archetype: ClientArchetype = ClientArchetype.query.get(
                self.campaign_id
            )

            return {
                "sequence_name": client_archetype.archetype,
                "example_prospect_name": self.example_prospect_name,
                "example_prospect_title": self.example_prospect_title,
                "example_prospect_company": self.example_prospect_company,
                "example_prospect_linkedin_url": self.example_prospect_linkedin_url,
                "example_message": self.example_message,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=setup/email?campaign_id={campaign_id}".format(
                    auth_token=client_sdr.auth_token, campaign_id=client_archetype.id
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
        sequence_name = fields.get("sequence_name")
        example_prospect_name = fields.get("example_prospect_name")
        example_prospect_title = fields.get("example_prospect_title")
        example_prospect_company = fields.get("example_prospect_company")
        example_prospect_linkedin_url = fields.get("example_prospect_linkedin_url")
        example_message = fields.get("example_message")
        direct_link = fields.get("direct_link")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.CAMPAIGN_ACTIVATED,
            client_id=client.id,
            base_message="🚀 SellScale AI activated a new campaign",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚀 SellScale AI activated a new campaign",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Sequence Preview:* {sequence_name}".format(
                            sequence_name=sequence_name if sequence_name else "-"
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Example Prospect*: <{}|{}> ({} @ {})".format(
                            "https://www." + example_prospect_linkedin_url,
                            example_prospect_name,
                            example_prospect_title,
                            example_prospect_company,
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "> 👥 {client_sdr_name} | Example message\n> _{example_first_generation}_".format(
                            client_sdr_name=client_sdr.name,
                            example_first_generation=example_message,
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": " "},
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Campaign",
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
