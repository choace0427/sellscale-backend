from typing import Optional
from src.client.models import Client, ClientSDR
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class EmailMultichanneledNotification(SlackNotificationClass):
    """A Slack notification that is sent when the user clicks on a link in an email

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to
    `from_email`: The email inbox which we are sending from
    `email_sent_subject`: The subject of the email that we sent
    `email_sent_body`: The body of the email that we sent

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "prospect_name",
        "prospect_message",
        "from_email",
        "email_sent_subject",
        "email_sent_body",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        from_email: Optional[str] = None,
        email_sent_subject: Optional[str] = None,
        email_sent_body: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.from_email = from_email
        self.email_sent_subject = email_sent_subject
        self.email_sent_body = email_sent_body

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
                "prospect_message": "Could we continue this conversation on email? My email is john@somecompany.ai.",
                "from_email": "youremail@sellscale.com",
                "email_sent_subject": "Following up on our LI conversation",
                "email_sent_body": f"Hey John,\nJust following up on our conversation from LinkedIn. I'd love to touch base and chat more about our AI Sales solution and how it could benefit your org.\nCheers,\n{client_sdr.name}",
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
                "prospect_message": prospect.li_last_message_from_prospect,
                "from_email": self.from_email,
                "email_sent_subject": self.email_sent_subject,
                "email_sent_body": self.email_sent_body,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=self.prospect_id if self.prospect_id else "",
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
        prospect_name = fields.get("prospect_name")
        prospect_message = fields.get("prospect_message")
        from_email = fields.get("from_email")
        email_sent_subject = fields.get("email_sent_subject")
        email_sent_body = (
            fields.get("email_sent_body", "").replace("\n", "\n>").strip("\n")
        )
        direct_link = fields.get("direct_link")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.EMAIL_MULTICHANNELED,
            client_id=client.id,
            base_message="📧 SellScale just multi-channeled",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📧 SellScale just multi-channeled",
                        "emoji": True,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "A prospect requested to be contacted via email. SellScale sent them an email on your behalf.",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*SDR*: {client_sdr.name} ({from_email})",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Prospect*: {prospect_name}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Message from {prospect_name}*:\n>{prospect_message}\n\n*Subject*:\n>{email_sent_subject}\n\n*Body*:\n>{email_sent_body}",
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
