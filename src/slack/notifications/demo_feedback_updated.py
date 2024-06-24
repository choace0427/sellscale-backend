import datetime
from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.client.models import DemoFeedback
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass
from src.utils.slack import URL_MAP


class DemoFeedbackUpdatedNotification(SlackNotificationClass):
    """A Slack notification that is sent whenever the SDR gives feedback on a Demo

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the feedback was given for
    `rating`: The rating that the ClientSDR gave the Demo
    `notes`: The notes that the ClientSDR gave the Demo
    `demo_status`: The status of the Demo
    `ai_adjustment`: The AI Adjustment of the Demo

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "rep",
        "rating",
        "prospect_name",
        "prospect_company",
        "archetype_name",
        "demo_date",
        "demo_status",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        rating: Optional[str] = None,
        notes: Optional[str] = None,
        demo_status: Optional[str] = None,
        ai_adjustment: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.rating = rating
        self.notes = notes
        self.demo_status = demo_status
        self.ai_adjustment = ai_adjustment

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
                "rep": client_sdr.name,
                "rating": "4",
                "notes": "It went pretty well during this call. They followed up with an email and we have another call scheduled. Not sure if they are totally convinced.",
                "ai_adjustment": "Let's change my targetting to only companies that have large sales outbound motions.",
                "prospect_name": "John Doe",
                "prospect_company": "SomeCompany",
                "archetype_name": "CEOs at AI Companies",
                "archetype_emoji": "🤖",
                "demo_date": datetime.datetime.now(),
                "demo_status": "OCCURRED",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            prospect: Prospect = Prospect.query.get(self.prospect_id)
            client_archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )

            return {
                "rep": client_sdr.name,
                "rating": self.rating,
                "notes": self.notes,
                "ai_adjustment": self.ai_adjustment,
                "prospect_name": prospect.full_name,
                "prospect_company": prospect.company,
                "archetype_name": client_archetype.archetype,
                "archetype_emoji": (
                    client_archetype.emoji if client_archetype.emoji else ""
                ),
                "demo_date": prospect.demo_date,
                "demo_status": self.demo_status,
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
        rep = fields.get("rep")
        rating = fields.get("rating")
        notes = fields.get("notes")
        ai_adjustment = fields.get("ai_adjustment")
        prospect_name = fields.get("prospect_name")
        prospect_company = fields.get("prospect_company")
        archetype_name = fields.get("archetype_name")
        archetype_emoji = fields.get("archetype_emoji")
        demo_date = fields.get("demo_date")
        demo_status = fields.get("demo_status")
        direct_link = fields.get("direct_link")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.DEMO_FEEDBACK_UPDATED,
            client_id=client.id,
            base_message=f"🎊 ✍️ UPDATED Demo Feedback",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🎊 ✍️ UPDATED Demo Feedback",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Rep*: {rep}\n*Rating*: {rating}\n*Notes*: {notes}\n*AI Adjustments*: `{ai_adjustments}`".format(
                            rating=rating,
                            rep=client_sdr.name,
                            notes=notes,
                            ai_adjustments=ai_adjustment,
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "*Prospect*: {prospect}\n*Company*: {company}\n*Persona*: {persona}\n*Date of demo*: {demo_date}\n*Demo*: {demo_status}".format(
                                prospect=prospect_name,
                                company=prospect_company,
                                persona=f"{archetype_emoji} {archetype_name}",
                                demo_date=demo_date.strftime("%B %d, %Y"),
                                demo_status=demo_status,
                            ),
                        }
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
