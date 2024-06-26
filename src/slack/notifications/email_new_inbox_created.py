from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class EmailNewInboxCreatedNotification(SlackNotificationClass):
    """A Slack notification that is sent when we create a new inbox for a client.

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `email`: The email address of the inbox that was created
    `warmup_finish_date`: The date that the inbox is expected to finish warming up

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "email",
        "warmup_finish_date",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        email: Optional[str] = None,
        warmup_finish_date: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.email = email
        self.warmup_finish_date = warmup_finish_date

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
                "email": "test@sellscale.com",
                "warmup_finish_date": "January 1, 2022",
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""

            return {
                "email": self.email,
                "warmup_finish_date": self.warmup_finish_date,
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Validate
        self.validate_required_fields(fields)

        # Get the fields
        email = fields.get("email")
        warmup_finish_date = fields.get("warmup_finish_date")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.EMAIL_NEW_INBOX_CREATED,
            client_id=client.id,
            base_message=f"New Inbox Created: {email}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📬 *New Inbox Created: {email}*\n✅ DKIM ✅ DMARC ✅ SPF ✅ Warming Enabled ✅ Domain Forwarding\nEstimated warmup date: {warmup_finish_date}",
                    },
                }
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
