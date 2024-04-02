from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class CampaignCompletedNotification(SlackNotificationClass):
    """A Slack notification that is sent when a campaign has finished initial outbounding.

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `campaign_id` (MANDATORY): The ID of the campaign that has finished initial outbounding.

    This class inherits from SlackNotificationClass.
    """

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        campaign_id: int = None,
    ):
        super().__init__(client_sdr_id, developer_mode)

        if not campaign_id:
            raise ValueError("campaign_id is a required parameter")
        self.campaign_id = campaign_id

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
                "number_of_prospects": 10,
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
            prospects: list[Prospect] = Prospect.query.filter(
                Prospect.archetype_id == self.campaign_id
            ).all()

            return {
                "sequence_name": client_archetype.archetype,
                "number_of_prospects": len(prospects),
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=setup/email?campaign_id={campaign_id}".format(
                    auth_token=client_sdr.auth_token, campaign_id=client_archetype.id
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        sequence_name = fields.get("sequence_name")
        number_of_prospects = fields.get("number_of_prospects")
        direct_link = fields.get("direct_link")
        if not sequence_name or not direct_link or not number_of_prospects:
            return False

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.CAMPAIGN_ACTIVATED,
            client_id=client.id,
            base_message="🏁 One of your campaigns has finished initial outbounding.",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f'🏁 "{sequence_name}" has finished initial outbounding.',
                        "emoji": True,
                    },
                },
                {
                    "type": "divider",
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Your campaign with {number_of_prospects} prospects has finished initial outbounding.",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "SellScale AI will be on standby to engage with any Prospects in this campaign. You can turn off this setting in the campaign settings.",
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
