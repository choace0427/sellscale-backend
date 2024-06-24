from typing import Optional
from src.client.models import Client, ClientSDR
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class LinkedinProspectRemovedNotification(SlackNotificationClass):
    """A Slack notification that is sent when the Prospect accepts a LinkedIn invite

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `prospect_id`: The ID of the Prospect that the AI replied to
    `old_status`: The old status of the Prospect
    `new_status`: The new status of the Prospect

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "prospect_name",
        "prospect_title",
        "prospect_company",
        "old_status",
        "new_status",
        "disqualification_reason",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        prospect_id: Optional[int] = None,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.prospect_id = prospect_id
        self.old_status = old_status
        self.new_status = new_status

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
                "old_status": "ACTIVE_CONVO_QUESTION",
                "new_status": "NOT_INTERESTED",
                "disqualification_reason": "Unresponsive",
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
                "prospect_title": prospect.title,
                "prospect_company": prospect.company,
                "old_status": self.old_status,
                "new_status": self.new_status,
                "disqualification_reason": prospect.disqualification_reason,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=prospect.id,
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        prospect_name = fields.get("prospect_name")
        prospect_title = fields.get("prospect_title")
        prospect_company = fields.get("prospect_company")
        old_status = fields.get("old_status")
        new_status = fields.get("new_status")
        disqualification_reason = fields.get("disqualification_reason")
        direct_link = fields.get("direct_link")

        #validate the required fields
        self.validate_required_fields(fields)

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Craft the message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🧹 SellScale has cleaned up your pipeline",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Prospect removed:* {prospect_name}".format(
                        prospect_name=prospect_name if prospect_name else "-",
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*AI label change:* `{old_status}` -> `{new_status}`".format(
                        old_status=old_status, new_status=new_status
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🧠 {type} Reason:* `{disqualification_reason}`".format(
                        type=(
                            "Disqualification"
                            if new_status == "NOT_QUALIFIED"
                            else "Not Interested"
                        ),
                        disqualification_reason=disqualification_reason,
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "🧳 Title: "
                        + str(prospect_title)
                        + " @ "
                        + str(prospect_company)[0:20]
                        + ("..." if len(prospect_company) > 20 else ""),
                        "emoji": True,
                    },
                    {
                        "type": "plain_text",
                        "text": "📌 SDR: " + client_sdr.name,
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
        ]

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.LINKEDIN_PROSPECT_REMOVED,
            client_id=client.id,
            base_message=f"🧹 SellScale has cleaned up your pipeline",
            blocks=blocks,
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
