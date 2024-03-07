import datetime
from app import db
from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.ai_requests.models import AIRequest
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class PipelineActivityDailyNotification(SlackNotificationClass):
    """A Slack notification that is sent whenever the SDR gives feedback on a Demo

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `title`: The title of task
    `description`: The description of the task
    `minutes_worked`: The number of minutes that the AI spent on this task

    This class inherits from SlackNotificationClass.
    """

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
    ):
        super().__init__(client_sdr_id, developer_mode)

        return

    def send_notification(self, preview_mode: bool) -> bool:
        """Sends a notification to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Args:
            preview_mode (bool): Whether or not the notification is being sent in preview mode. Preview mode sends to a 'dummy' message to the channel.

        Returns:
            bool: Whether or not the message was successfully sent
        """

        data_query = f"""
            SELECT
                client_sdr.id rep_id,
                client_sdr.name rep,
                client_archetype.archetype campaign,
                client_archetype.emoji campaign_emoji,
                client_archetype.linkedin_active linkedin_active,
                client_archetype.email_active email_active,
                count(DISTINCT prospect.id) num_prospects,
                count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'SENT_OUTREACH'
                    AND prospect_status_records.created_at > now() - '24 hours'::interval) "linkedin_sent_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACCEPTED'
                    AND prospect_status_records.created_at > now() - '24 hours'::interval) "linkedin_accepted_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACTIVE_CONVO'
                    AND prospect_status_records.created_at > now() - '24 hours'::interval) "linkedin_active_convo_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACTIVE_CONVO_SCHEDULING'
                    AND prospect_status_records.created_at > now() - '24 hours'::interval) "linkedin_scheduling_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'DEMO_SET'
                    AND prospect_status_records.created_at > now() - '24 hours'::interval) "linkedin_demo_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'SENT_OUTREACH'
                    AND prospect_email_status_records.created_at > now() - '24 hours'::interval) "email_sent_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'EMAIL_OPENED'
                    AND prospect_email_status_records.created_at > now() - '24 hours'::interval) "email_opened_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'ACCEPTED'
                    AND prospect_email_status_records.created_at > now() - '24 hours'::interval) "email_clicked_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'ACTIVE_CONVO'
                    AND prospect_email_status_records.created_at > now() - '24 hours'::interval) "email_replied_24_hrs",
                count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'DEMO_SET'
                    AND prospect_email_status_records.created_at > now() - '24 hours'::interval) "email_demo_24_hrs"
            FROM
                client_sdr
                LEFT JOIN client_archetype ON client_archetype.client_sdr_id = client_sdr.id
                LEFT JOIN prospect ON prospect.archetype_id = client_archetype.id
                LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id
                LEFT JOIN prospect_email ON prospect_email.prospect_id = prospect.id
                LEFT JOIN prospect_email_status_records ON prospect_email_status_records.prospect_email_id = prospect_email.id
                LEFT JOIN smartlead_webhook_payloads ON cast(smartlead_webhook_payloads.smartlead_payload ->> 'campaign_id' AS integer) = client_archetype.id
            WHERE
                client_archetype.active
                AND (client_archetype.linkedin_active
                    OR client_archetype.email_active)
                AND client_sdr.id = {self.client_sdr_id}
            GROUP BY
                1,
                2,
                3,
                4
        """

        def get_preview_fields() -> dict:
            """Gets the fields to be used in the preview message."""
            return {
                "data": [
                    {
                        "rep_id": -1,
                        "rep": "John Doe",
                        "campaign": "CEOs at AI Companies",
                        "campaign_emoji": "🤖",
                        "linkedin_active": True,
                        "email_active": True,
                        "num_prospects": 100,
                        "linkedin_sent_24_hrs": 10,
                        "linkedin_accepted_24_hrs": 5,
                        "linkedin_active_convo_24_hrs": 3,
                        "linkedin_scheduling_24_hrs": 2,
                        "linkedin_demo_24_hrs": 1,
                        "email_sent_24_hrs": 20,
                        "email_opened_24_hrs": 15,
                        "email_clicked_24_hrs": 10,
                        "email_replied_24_hrs": 5,
                        "email_demo_24_hrs": 2,
                    }
                ]
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            data = db.session.execute(data_query).fetch_all()
            data = [dict(row) for row in data]

            return {"data": data}

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        data = fields.get("data")
        if not data:
            return False

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Create the message
        # Header
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📝 Daily Drilldown for {client_sdr.name}",
                    "emoji": True,
                },
            },
            {
                "type": "divider",
            },
        ]

        # Campaigns
        for campaign in data:
            campaign_blocks = []
            campaign_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{campaign.get('campaign_emoji')} *{campaign['campaign']}:*",
                        "emoji": True,
                    },
                }
            )
            if campaign.get("linkedin_active"):
                sent = campaign.get("linkedin_sent_24_hrs")
                accepted = campaign.get("linkedin_accepted_24_hrs")
                active_convo = campaign.get("linkedin_active_convo_24_hrs")
                scheduling = campaign.get("linkedin_scheduling_24_hrs")
                demo = campaign.get("linkedin_demo_24_hrs")
                campaign_blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f">*LinkedIn Summary:*\n> ➡️ Sent Today: *{sent}* | ✅ Accepted Invite: *{accepted}* | ↩️ New Replies: *{active_convo}* | ⏱️ Scheduling: *{scheduling}* | 🎉 Demos Set: *{demo}*",
                            "emoji": True,
                        },
                    }
                )
            if campaign.get("email_active"):
                sent = campaign.get("email_sent_24_hrs")
                opened = campaign.get("email_opened_24_hrs")
                clicked = campaign.get("email_clicked_24_hrs")
                replied = campaign.get("email_replied_24_hrs")
                demo = campaign.get("email_demo_24_hrs")
                campaign_blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f">*Email Summary:*\n> ➡️ Sent Today: *{sent}* | 📬 Opened: *{opened}* | 🔗 Clicked: *{clicked}* | ↩️ Replied: *{replied}* | 🎉 Demos Set: *{demo}*",
                            "emoji": True,
                        },
                    }
                )

            blocks.extend(campaign_blocks)

        # Disclaimer
        blocks.extend(
            [
                {
                    "type": "divider",
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"_Disclaimer: The figures above represent the activity from all *active campaigns* in the past 24 hours. Please be aware that the values may not exclusively correspond to the most recent interactions; values such as responses, scheduling, demos, etc, can be caused by any past engagement within the campaign._",
                        },
                    ],
                },
            ]
        )

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.PIPELINE_ACTIVITY_DAILY,
            client_id=client.id,
            base_message=f"View your daily pipeline activity for {client_sdr.name}",
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
