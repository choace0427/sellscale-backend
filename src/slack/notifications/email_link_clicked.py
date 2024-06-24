from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import WebhookDict, slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class EmailLinkClickedNotification(SlackNotificationClass):
    """A Slack notification that is sent when the user clicks on a link in an email

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to
    `link_clicked`: The link that was clicked

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "prospect_name",
        "prospect_title",
        "prospect_company",
        "archetype_name",
        "archetype_emoji",
        "direct_link",
        "link_clicked",
        "initial_send_date",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        link_clicked: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.link_clicked = link_clicked

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
                "archetype_name": "CEOs at AI Companies",
                "archetype_emoji": "🤖",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token,
                ),
                "link_clicked": "https://www.sellscale.com",
                "initial_send_date": "January 1, 2022",
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            prospect: Prospect = Prospect.query.get(self.prospect_id)
            archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )
            prospect_email: ProspectEmail = ProspectEmail.query.filter_by(
                id=prospect.approved_prospect_email_id
            ).first()
            generated_message: GeneratedMessage = GeneratedMessage.query.filter_by(
                id=prospect_email.personalized_body
            ).first()
            initial_send_date = "-"
            if generated_message:
                initial_send_date = generated_message.created_at.strftime("%B %d, %Y")

            return {
                "prospect_name": prospect.full_name,
                "prospect_title": prospect.title,
                "prospect_company": prospect.company,
                "archetype_name": archetype.archetype,
                "archetype_emoji": archetype.emoji if archetype.emoji else "",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=self.prospect_id if self.prospect_id else "",
                ),
                "link_clicked": self.link_clicked,
                "initial_send_date": initial_send_date,
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
        archetype_name = fields.get("archetype_name")
        archetype_emoji = fields.get("archetype_emoji")
        direct_link = fields.get("direct_link")
        link_clicked = fields.get("link_clicked")
        initial_send_date = fields.get("initial_send_date")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.EMAIL_LINK_CLICKED,
            client_id=client.id,
            base_message="🔗 A prospect clicked your link!",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🔗 {prospect_name} clicked your link",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Campaign:* {emoji} {persona}".format(
                            persona=archetype_name if archetype_name else "-",
                            emoji=archetype_emoji,
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Title:* {title}\n*Company:* {company}".format(
                            title=prospect_title if prospect_title else "-",
                            company=prospect_company if prospect_company else "-",
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Link Clicked:* {link}".format(
                            link=link_clicked,
                        ),
                    },
                },
                {"type": "divider"},
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
