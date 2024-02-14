from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.message_generation.models import GeneratedMessage
from src.prospecting.models import Prospect
from src.li_conversation.models import LinkedinConversationEntry
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class LinkedInDemoSetNotification(SlackNotificationClass):
    """A Slack notification that is sent when the Prospect sets demo on LinkedIn

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to
    `is_hand_off`: Whether or not the notification is for the conversation was handed off

    This class inherits from SlackNotificationClass.
    """

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        is_hand_off: Optional[bool] = False,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.is_hand_off = is_hand_off

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
                "prospect_icp_fit_reason": "(✅ Prospect Industry: Software - AI) (✅ Prospect Seniority: CEO)",
                "archetype_name": "CEOs at AI Companies",
                "archetype_emoji": "🤖",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token,
                ),
                "conversation": [
                    f"*{client_sdr.name}:* Hey John, if utilizing AI is a priority for you, I'd love to connect and share how we're helping other CEOs at AI companies like yours. Also, Go Bears!",
                    f"*John Doe:* Sounds good, let's schedule a time to chat?",
                ],
                "initial_send_date": "January 1, 2024",
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            prospect: Prospect = Prospect.query.get(self.prospect_id)
            client_archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )
            urn_id = prospect.li_conversation_urn_id
            convo: list[LinkedinConversationEntry] = (
                LinkedinConversationEntry.query.filter_by(
                    conversation_url=f"https://www.linkedin.com/messaging/thread/{urn_id}/"
                )
                .order_by(LinkedinConversationEntry.created_at.desc())
                .limit(5)
                .all()
            )
            generated_message: GeneratedMessage = GeneratedMessage.query.filter_by(
                id=prospect.approved_outreach_message_id
            ).first()

            # Get the conversation
            conversation = []
            for c in reversed(
                convo
            ):  # Reverse the conversation so that the most recent message is at the bottom
                conversation.append(f"*{c.author}:* {c.message}")

            return {
                "prospect_name": prospect.full_name,
                "prospect_title": prospect.title,
                "prospect_company": prospect.company,
                "prospect_icp_fit_reason": prospect.icp_fit_reason,
                "archetype_name": client_archetype.archetype,
                "archetype_emoji": client_archetype.emoji,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=prospect.id,
                ),
                "conversation": conversation,
                "initial_send_date": generated_message.created_at.strftime("%B %d, %Y"),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            # If we're not in preview mode, we need to ensure that the required fields are set
            if not self.prospect_id:
                return False
            fields = get_fields()

        # Get the fields
        prospect_name = fields.get("prospect_name")
        prospect_title = fields.get("prospect_title")
        prospect_company = fields.get("prospect_company")
        prospect_icp_fit_reason = fields.get("prospect_icp_fit_reason")
        archetype_name = fields.get("archetype_name")
        archetype_emoji = fields.get("archetype_emoji")
        direct_link = fields.get("direct_link")
        conversation = fields.get("conversation")
        initial_send_date = fields.get("initial_send_date")

        if (
            not prospect_name
            or not prospect_title
            or not prospect_company
            or not prospect_icp_fit_reason
            or not archetype_name
            or not archetype_emoji
            or not direct_link
            or not conversation
            or not initial_send_date
        ):
            return False

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        header = f"🎉 {prospect_name} set a time to demo!!"
        base_message = f"{prospect_name} set a time to demo at {prospect_company} ({archetype_name})."
        if self.is_hand_off:
            header = f"🎉 {prospect_name} was handed off internally!!"
            base_message = f"{prospect_name} was handed off at {prospect_company} ({archetype_name})."

        # Craft the message blocks
        message_blocks: list[dict] = []
        message_blocks.extend(
            [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": header,
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
                        "text": "*Title:* {title}\n*Company:* {company}".format(
                            title=prospect_title if prospect_title else "-",
                            company=prospect_company if prospect_company else "-",
                        ),
                    },
                },
            ]
        )

        for message in conversation:
            message_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{message}",
                    },
                }
            )

        message_blocks.extend(
            [
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
                            "text": "📤 Outbound channel: LinkedIn",
                            "emoji": True,
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*ICP fit reason:* {}".format(prospect_icp_fit_reason),
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
                            "text": "View Convo in Sight",
                            "emoji": True,
                        },
                        "value": direct_link,
                        "url": direct_link,
                        "action_id": "button-action",
                    },
                },
            ]
        )

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.LINKEDIN_DEMO_SET,
            client_id=client.id,
            base_message=base_message,
            blocks=message_blocks,
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
