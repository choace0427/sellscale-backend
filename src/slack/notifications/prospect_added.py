from typing import Optional
from src.client.models import Client, ClientSDR
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    slack_bot_send_message,
)
from src.slack.slack_notification_class import SlackNotificationClass
import random


class ProspectAddedNotification(SlackNotificationClass):
    """A Slack notification that is sent whenever the SDR gives feedback on a Demo

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the feedback was given for

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "num_new_prospects",
        "estimated_savings",
        "persona_or_segment_string",
        "top_titles",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        num_new_prospects: Optional[int] = 0,
        estimated_savings: Optional[float] = 0.0,
        persona_or_segment_string: Optional[str] = "",
        top_titles: Optional[list[str]] = [""],
        company_size_str: Optional[str] = "",
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.num_new_prospects = num_new_prospects
        self.estimated_savings = estimated_savings
        self.persona_or_segment_string = persona_or_segment_string
        self.top_titles = top_titles
        self.company_size_str = company_size_str

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

            # Get a dummy estimated_savings field by using a random number between 90 and 150
            estimated_savings = round(random.uniform(90, 150), 2)

            # Randomly choose the persona_or_segment_string to be either "Persona" or "Segment"
            persona_or_segment_string = (
                "Persona: CEOs at AI Companies"
                if random.choice([True, False])
                else "Segment: AI Companies based in San Francisco"
            )

            return {
                "num_new_prospects": 83,
                "estimated_savings": estimated_savings,
                "persona_or_segment_string": persona_or_segment_string,
                "top_titles": [["CEO", 80], ["Founder and CEO", 3]],
                "company_size_str": 216,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=contacts/".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            return {
                "num_new_prospects": self.num_new_prospects,
                "estimated_savings": self.estimated_savings,
                "persona_or_segment_string": self.persona_or_segment_string,
                "top_titles": self.top_titles,
                "company_size_str": self.company_size_str,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=contacts/".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        num_new_prospects = fields.get("num_new_prospects")
        estimated_savings = fields.get("estimated_savings")
        persona_or_segment_string = fields.get("persona_or_segment_string")
        top_titles = fields.get("top_titles")
        company_size_str = fields.get("company_size_str")
        direct_link = fields.get("direct_link")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.PROSPECT_ADDED,
            client_id=client.id,
            base_message=f"🚢 {num_new_prospects} new prospects added to your prospect list!",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚢 {x} new prospects added to your prospect list!".format(
                            x=num_new_prospects
                        ),
                        "emoji": True,
                    },
                },
                {"type": "divider"},
                # {
                #     "type": "section",
                #     "text": {
                #         "type": "mrkdwn",
                #         "text": f"🤑 SellScale just helped save `${estimated_savings}` of finding contacts.",
                #     },
                # },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "User: {user} ({company})".format(
                                user=client_sdr.name, company=client.company
                            ),
                        },
                        {
                            "type": "mrkdwn",
                            "text": "{persona_or_segment_string}".format(
                                persona_or_segment_string=persona_or_segment_string
                            ),
                        },
                        {
                            "type": "mrkdwn",
                            "text": "Top Titles: {top_titles}".format(
                                top_titles=", ".join(
                                    [
                                        "{title} ({count})".format(
                                            title=title, count=count
                                        )
                                        for title, count in top_titles
                                    ]
                                )
                            ),
                        },
                        # {
                        #     "type": "mrkdwn",
                        #     "text": "Company Median Size: {company_size_str}".format(
                        #         company_size_str=company_size_str
                        #     ),
                        # },
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
                            "text": "View Contacts in Sight",
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
