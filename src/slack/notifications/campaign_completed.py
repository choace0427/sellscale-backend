from app import db
from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class CampaignCompletedNotification(SlackNotificationClass):
    """A Slack notification that is sent when a campaign has finished initial outbounding.

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `campaign_id` (MANDATORY): The ID of the campaign that has finished initial outbounding.

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "sequence_name",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        campaign_id: int = None,
    ):
        super().__init__(client_sdr_id, developer_mode)

        if not campaign_id:
            raise ValueError("campaign_id is a required parameter")
        self.campaign_id = campaign_id

        return

    def send_notification(self, preview_mode: bool) -> bool:
        """Sends a notification to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Args:
            preview_mode (bool): Whether or not the notification is being sent in preview mode. Preview mode sends to a 'dummy' message to the channel.

        Returns:
            bool: Whether or not the message was successfully sent
        """
        linkedin_stats_query = f"""SELECT
                                    count(distinct p.id) filter (where psr.to_status = 'SENT_OUTREACH'),
                                    count(distinct p.id) filter (where psr.to_status = 'ACCEPTED'),
                                    count(distinct p.id) filter (where psr.to_status::text ILIKE '%ACTIVE_CONVO%'),
                                    count(distinct p.id) filter (where psr.to_status::text ILIKE '%DEMO%')
                                FROM
                                    client_archetype ca
                                    LEFT JOIN prospect p ON p.archetype_id = ca.id
                                    LEFT JOIN prospect_status_records psr ON psr.prospect_id = p.id
                                where
                                    archetype_id = {self.campaign_id};
        """
        email_stats_query = f"""SELECT
                                    count(DISTINCT p.id) FILTER (WHERE pesr.to_status = 'SENT_OUTREACH'),
                                    count(DISTINCT p.id) FILTER (WHERE pesr.to_status = 'EMAIL_OPENED'),
                                    count(DISTINCT p.id) FILTER (WHERE pesr.to_status::text ILIKE '%ACTIVE_CONVO%'),
                                    count(DISTINCT p.id) FILTER (WHERE pesr.to_status::text ILIKE '%DEMO%')
                                FROM
                                    client_archetype ca
                                    LEFT JOIN prospect p ON p.archetype_id = ca.id
                                    LEFT JOIN prospect_email pe on p.approved_prospect_email_id = pe.id
                                    LEFT JOIN prospect_email_status_records pesr ON pesr.prospect_email_id = pe.id
                                WHERE
                                    archetype_id = {self.campaign_id};
        """

        def get_preview_fields() -> dict:
            """Gets the fields to be used in the preview message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            return {
                "sequence_name": "CEOs at AI Companies",
                "sequence_emoji": "🤖 ",
                "stats_string": f"*LinkedIn Summary:*\n➡️ Sent: *20* | ✅ Accepted: *15* | ↩️ Replies: *8* | 🎉 Demos: *5*\n*Email Summary:*\n➡️ Sent: *10* | 📬 Opens: *7* | ↩️ Replies: *4* | 🎉 Demos: *3*",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            client_archetype: ClientArchetype = ClientArchetype.query.get(
                self.campaign_id
            )

            stats_string: str = ""

            # If LinkedIn is active
            if client_archetype.linkedin_active:
                # Get the LinkedIn stats
                linkedin_stats = db.session.execute(linkedin_stats_query).fetchall()
                sent = linkedin_stats[0][0]
                accepted = linkedin_stats[0][1]
                active_convo = linkedin_stats[0][2]
                demo = linkedin_stats[0][3]
                stats_string = f"*LinkedIn Summary:*\n➡️ Sent: *{sent}* | ✅ Accepted: *{accepted}* | ↩️ Replies: *{active_convo}* | 🎉 Demos: *{demo}*\n"

            # If email is active
            if client_archetype.email_active:
                # Get the email stats
                db.session.execute(email_stats_query)
                email_stats = db.session.fetchone()
                sent = email_stats[0][0]
                opened = email_stats[0][1]
                active_convo = email_stats[0][2]
                demo = email_stats[0][3]
                stats_string += f"*Email Summary:*\n➡️ Sent: *{sent}* | 📬 Opens: *{opened}* | ↩️ Replies: *{active_convo}* | 🎉 Demos: *{demo}*"

            return {
                "sequence_name": client_archetype.archetype,
                "sequence_emoji": (
                    client_archetype.emoji if client_archetype.emoji else ""
                ),
                "stats_string": stats_string,
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=setup/email?campaign_id={campaign_id}".format(
                    auth_token=client_sdr.auth_token, campaign_id=client_archetype.id
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
        sequence_name = fields.get("sequence_name")
        sequence_emoji = fields.get("sequence_emoji")
        stats_string = fields.get("stats_string")
        direct_link = fields.get("direct_link")

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.CAMPAIGN_ACTIVATED,
            client_id=client.id,
            base_message="🏁 One of your campaigns is complete.",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🏁 Campaign complete: {sequence_emoji}{sequence_name}",
                        "emoji": True,
                    },
                },
                {
                    "type": "divider",
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": stats_string,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Rep:* {client_sdr.name}",
                    },
                },
                {  # Add footer note
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Followups may still be in progress.",
                            "emoji": True,
                        }
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": " "},
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Campaign",
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
