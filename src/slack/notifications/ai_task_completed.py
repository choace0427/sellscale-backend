import datetime
from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.ai_requests.models import AIRequest
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class AITaskCompletedNotification(SlackNotificationClass):
    """A Slack notification that is sent whenever the SDR gives feedback on a Demo

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `title`: The title of task
    `description`: The description of the task
    `minutes_worked`: The number of minutes that the AI spent on this task

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "title",
        "contact",
        "request_date",
        "completed_date",
        "dashboard_url",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        title: Optional[str] = None,
        description: Optional[str] = None,
        minutes_worked: Optional[int] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.title = title
        self.description = description
        self.minutes_worked = minutes_worked

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
                "title": "Remove Security Ops titles",
                "minutes_worked": 5,
                "description": "Removed 500+ instances of 'Security Operations' titles",
                "contact": client_sdr.name,
                "request_date": datetime.datetime.now().strftime("%B %d, %Y"),
                "completed_date": datetime.datetime.now().strftime("%B %d, %Y"),
                "dashboard_url": (
                    "https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
                    + client_sdr.auth_token
                    + "&redirect=ai-request"
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            request: AIRequest = AIRequest.query.get(self.client_sdr_id)

            return {
                "title": self.title,
                "minutes_worked": self.minutes_worked,
                "description": self.description if self.description else "-",
                "contact": client_sdr.name,
                "request_date": (
                    request.created_at.strftime("%B %d, %Y") if request else "-"
                ),
                "completed_date": datetime.datetime.now().strftime("%B %d, %Y"),
                "dashboard_url": (
                    "https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
                    + client_sdr.auth_token
                    + "&redirect=ai-request"
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
        title = fields.get("title")
        minutes_worked = fields.get("minutes_worked")
        description = fields.get("description")
        contact = fields.get("contact")
        request_date = fields.get("request_date")
        completed_date = fields.get("completed_date")
        dashboard_url = fields.get("dashboard_url")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.AI_TASK_COMPLETED,
            client_id=client.id,
            base_message=f"✅ SellScale AI completed a new task for you!",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ SellScale AI completed a new task for you!",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Task:* {title}".format(title=title if title else "-"),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*AI Run Time:* {minutes_worked} minutes ⏱️".format(
                            minutes_worked=minutes_worked if minutes_worked else "-",
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Description:* {description}".format(
                            description=description if description else "-"
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Contact: {sdr}".format(
                                sdr=client_sdr.name,
                            ),
                            "emoji": True,
                        },
                        {
                            "type": "plain_text",
                            "text": "Date Requested: {request_date}".format(
                                request_date=request_date,
                            ),
                            "emoji": True,
                        },
                        {
                            "type": "plain_text",
                            "text": "Date Completed: {complete_date}".format(
                                complete_date=datetime.datetime.now().strftime(
                                    "%B %d, %Y"
                                ),
                            ),
                            "emoji": True,
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
                            "text": "View in Dashboard →",
                            "emoji": True,
                        },
                        "url": dashboard_url,
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
