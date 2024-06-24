from typing import Optional
from src.client.models import Client, ClientSDR
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class LinkedInConnectionDisconnected(SlackNotificationClass):
    """A Slack notification that is sent when the user clicks on a link in an email

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to

    This class inherits from SlackNotificationClass.
    """

    required_fields = {"num_messages_in_queue", "direct_link"}

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        num_messages_in_queue: Optional[int] = 0,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.num_messages_in_queue = num_messages_in_queue

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
                "num_messages_in_queue": 12,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=settings/linkedin".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            return {
                "num_messages_in_queue": self.num_messages_in_queue,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=settings/linkedin".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        num_messages_in_queue = fields.get("num_messages_in_queue")
        direct_link = fields.get("direct_link")
        
        #validate the required fields
        self.validate_required_fields(fields)

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.LINKEDIN_CONNECTION_DISCONNECTED,
            client_id=client.id,
            base_message=f"🚨 LinkedIn Disconnected for {client_sdr.name}",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 LinkedIn Disconnected for {client_sdr.name}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Please reconnect your LinkedIn as soon as possible. There are currently *{num_messages_in_queue}* prospects in the LinkedIn outbound queue. There may be more requiring bumps, replies, etc.".format(
                            num_messages_in_queue=num_messages_in_queue,
                        ),
                    },
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
                            "text": "Reconnect in Settings",
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
