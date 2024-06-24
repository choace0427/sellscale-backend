from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class EmailProspectRepliedNotification(SlackNotificationClass):
    """A Slack notification that is sent when the Prospect replies to an email.

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that responded
    `email_sent_subject`: The subject of the email that was sent
    `email_sent_body`: The body of the email that was sent
    `email_reply_body`: The body of the reply from the Prospect

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "prospect_name",
        "prospect_title",
        "prospect_company",
        "prospect_email",
        "archetype_name",
        "archetype_emoji",
        "email_sent_subject",
        "email_sent_body",
        "email_reply_body",
        "direct_link",
        "initial_send_date",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        email_sent_subject: Optional[str] = None,
        email_sent_body: Optional[str] = None,
        email_reply_body: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.email_sent_subject = email_sent_subject
        self.email_sent_body = email_sent_body
        self.email_reply_body = email_reply_body

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
                "prospect_email": "john@somecompany.ai",
                "archetype_name": "CEOs at AI Companies",
                "archetype_emoji": "🤖",
                "email_sent_subject": "Supercharge SomeCompany's sales with AI",
                "email_sent_body": f"\nHey John,\nLike many industries, sales oftentimes involves many hours of rote work. As a forward-thinking CEO leveraging AI in your respective industry, have you considered using AI to boost your outbound?\nIf this sounds interesting, *let's chat*?\nBest,\n{client_sdr.name}",
                "email_reply_body": f"\nHey,\nI'm interested. Let's chat.\nBest,\nJohn Doe",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token,
                ),
                "initial_send_date": "January 1, 2022",
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            prospect: Prospect = Prospect.query.get(self.prospect_id)
            prospect_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )
            client_archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )

            generated_message: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_body
            )
            if generated_message:
                send_date = (  # Ideally we want to use the date_sent field, but some legacy code made it such that older messages don't have this field populated correctly. This is a safeguard.
                    generated_message.date_sent.strftime("%B %d, %Y")
                    if generated_message.date_sent
                    else generated_message.created_at.strftime("%B %d, %Y")
                )
            else:
                send_date = "-"

            if not self.email_sent_body or not self.email_reply_body:
                raise ValueError(
                    "Illegal arguments for EmailProspectResponded notification: Missing email bodies."
                )

            return {
                "prospect_name": prospect.full_name,
                "prospect_title": prospect.title,
                "prospect_company": prospect.company,
                "prospect_email": prospect.email,
                "archetype_name": client_archetype.archetype,
                "archetype_emoji": (
                    client_archetype.emoji if client_archetype.emoji else ""
                ),
                "email_sent_subject": self.email_sent_subject,
                "email_sent_body": self.email_sent_body,
                "email_reply_body": self.email_reply_body,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=prospect.id,
                ),
                "initial_send_date": send_date,
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
        prospect_email = fields.get("prospect_email")
        archetype_name = fields.get("archetype_name")
        archetype_emoji = fields.get("archetype_emoji")
        email_sent_subject = fields.get("email_sent_subject")
        email_sent_body = fields.get("email_sent_body", "").replace("\n", "\n>")
        email_reply_body = fields.get("email_reply_body", "").replace("\n", "\n>")
        direct_link = fields.get("direct_link")
        initial_send_date = fields.get("initial_send_date")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.EMAIL_PROSPECT_REPLIED,
            client_id=client.id,
            base_message=f"🙌🏽 {prospect_name} responded to your email!",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🙌🏽 {prospect_name} responded to your email!",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Persona:* {emoji} {persona}".format(
                            persona=archetype_name if archetype_name else "-",
                            emoji=archetype_emoji,
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Title:* {title}\n*Company:* {company}\n*Prospect Email:* {prospect_email}".format(
                            title=prospect_title if prospect_title else "-",
                            company=prospect_company if prospect_company else "-",
                            prospect_email=prospect_email,
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Email Subject*:\n>{email_sent_subject}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Sent Email*:\n{email_sent_body}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Reply*:\n{email_reply_body}",
                    },
                },
                {  # Add SDR information
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
                            "text": "📆 Initial Send: {date_sent}".format(
                                date_sent=initial_send_date,
                            ),
                            "emoji": True,
                        },
                        {
                            "type": "plain_text",
                            "text": "📤 Outbound channel: Email",
                            "emoji": True,
                        },
                    ],
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
