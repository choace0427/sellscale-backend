from app import db
from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB


class SlackNotificationType(Enum):
    """The types of Slack notifications that can be sent"""

    # LINKEDIN
    LINKEDIN_CONNECTION_CONNECTED = "LINKEDIN_CONNECTION_CONNECTED"
    LINKEDIN_CONNECTION_DISCONNECTED = "LINKEDIN_CONNECTION_DISCONNECTED"
    LINKEDIN_INVITE_ACCEPTED = "LINKEDIN_INVITE_ACCEPTED"
    LINKEDIN_MESSAGE_RECEIVED = "LINKEDIN_MESSAGE_RECEIVED"
    LINKEDIN_PROSPECT_RESPONDED = "LINKEDIN_PROSPECT_RESPONDED"
    LINKEDIN_PROSPECT_SCHEDULING = "LINKEDIN_PROSPECT_SCHEDULING"
    LINKEDIN_PROSPECT_REMOVED = "LINKEDIN_PROSPECT_REMOVED"
    LINKEDIN_DEMO_SET = "LINKEDIN_DEMO_SET"
    LINKEDIN_AI_REPLY = "LINKEDIN_AI_REPLY"
    LINKEDIN_MULTI_THREAD = "LINKEDIN_MULTI_THREAD"

    # EMAIL
    AI_REPLY_TO_EMAIL = "AI_REPLY_TO_EMAIL"
    EMAIL_LINK_CLICKED = "EMAIL_LINK_CLICKED"
    EMAIL_PROSPECT_REPLIED = "EMAIL_PROSPECT_REPLIED"
    EMAIL_MULTICHANNELED = "EMAIL_MULTICHANNELED"
    EMAIL_NEW_INBOX_CREATED = "EMAIL_NEW_INBOX_CREATED"

    # GENERAL
    DEMO_FEEDBACK_COLLECTED = "DEMO_FEEDBACK_COLLECTED"
    DEMO_FEEDBACK_UPDATED = "DEMO_FEEDBACK_UPDATED"
    AI_TASK_COMPLETED = "AI_TASK_COMPLETED"
    CAMPAIGN_ACTIVATED = "CAMPAIGN_ACTIVATED"
    CAMPAIGN_COMPLETED = "CAMPAIGN_COMPLETED"
    PROSPECT_ADDED = "PROSPECT_ADDED"
    PROSPECT_SNOOZED = "PROSPECT_SNOOZED"
    ASSET_CREATED = "ASSET_CREATED"
    PIPELINE_ACTIVITY_DAILY = "PIPELINE_ACTIVITY_DAILY"

    def name(self):
        return get_slack_notification_type_metadata()[self].get("name")

    def description(self):
        return get_slack_notification_type_metadata()[self].get("description")

    def get_class(self):
        return get_slack_notification_type_metadata()[self].get("class")

    def get_outbound_channel(self):
        return get_slack_notification_type_metadata()[self].get("outbound_channel")


def get_slack_notification_type_metadata():
    from src.slack.notifications.email_ai_reply_notification import (
        EmailAIReplyNotification,
    )
    from src.slack.notifications.linkedin_invite_accepted import (
        LinkedInInviteAcceptedNotification,
    )
    from src.slack.notifications.linkedin_message_received import (
        LinkedInMessageReceivedNotification,
    )
    from src.slack.notifications.linkedin_prospect_responded import (
        LinkedinProspectRespondedNotification,
    )
    from src.slack.notifications.linkedin_demo_set import (
        LinkedInDemoSetNotification,
    )
    from src.slack.notifications.email_link_clicked import EmailLinkClickedNotification
    from src.slack.notifications.demo_feedback_updated import (
        DemoFeedbackUpdatedNotification,
    )
    from src.slack.notifications.demo_feedback_collected import (
        DemoFeedbackCollectedNotification,
    )
    from src.slack.notifications.linkedin_prospect_scheduling import (
        LinkedinProspectSchedulingNotification,
    )
    from src.slack.notifications.email_prospect_replied import (
        EmailProspectRepliedNotification,
    )
    from src.slack.notifications.email_multichanneled import (
        EmailMultichanneledNotification,
    )
    from src.slack.notifications.ai_task_completed import (
        AITaskCompletedNotification,
    )
    from src.slack.notifications.linkedin_prospect_removed import (
        LinkedinProspectRemovedNotification,
    )
    from src.slack.notifications.linkedin_connection_connected import (
        LinkedInConnectionConnected,
    )
    from src.slack.notifications.campaign_activated import (
        CampaignActivatedNotification,
    )
    from src.slack.notifications.campaign_completed import (
        CampaignCompletedNotification,
    )
    from src.slack.notifications.linkedin_ai_reply import (
        LinkedInAIReplyNotification,
    )
    from src.slack.notifications.prospect_added import (
        ProspectAddedNotification,
    )
    from src.slack.notifications.linkedin_connection_disconnected import (
        LinkedInConnectionDisconnected,
    )
    from src.slack.notifications.prospect_snoozed import (
        ProspectSnoozedNotification,
    )
    from src.slack.notifications.linkedin_multithread import (
        LinkedInMultiThreadNotification,
    )
    from src.slack.notifications.asset_created import AssetCreatedNotification
    from src.slack.notifications.email_new_inbox_created import (
        EmailNewInboxCreatedNotification,
    )
    from src.slack.notifications.pipeline_activity_daily import (
        PipelineActivityDailyNotification,
    )

    map_slack_notification_type_to_metadata = {
        SlackNotificationType.LINKEDIN_INVITE_ACCEPTED: {
            "name": "LinkedIn Invite Accepted",
            "description": "A Slack notification that is sent when the Prospect accepts a LinkedIn invite",
            "class": LinkedInInviteAcceptedNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_MESSAGE_RECEIVED: {
            "name": "LinkedIn Message Recieved",
            "description": "A Slack notification that is sent when the Prospect has sent you any message through LinkedIn",
            "class": LinkedInMessageReceivedNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_PROSPECT_RESPONDED: {
            "name": "Linkedin Prospect Responded",
            "description": "A Slack notification that is sent when a Prospect has responded to your LinkedIn message for the first time.",
            "class": LinkedinProspectRespondedNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_PROSPECT_SCHEDULING: {
            "name": "LinkedIn Prospect Scheduling",
            "description": "A Slack notification that is sent when a Prospect is scheduling a meeting with you on LinkedIn",
            "class": LinkedinProspectSchedulingNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_PROSPECT_REMOVED: {
            "name": "Linkedin Prospect Removed",
            "description": "A Slack notification that is sent when a Prospect is removed from your pipeline",
            "class": LinkedinProspectRemovedNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_DEMO_SET: {
            "name": "LinkedIn Demo Set",
            "description": "A Slack notification that is sent when a Prospect schedules a demo through LinkedIn",
            "class": LinkedInDemoSetNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_AI_REPLY: {
            "name": "AI Reply to LinkedIn",
            "description": "A Slack notification that is sent when the AI replies to a LinkedIn message",
            "class": LinkedInAIReplyNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_CONNECTION_CONNECTED: {
            "name": "LinkedIn Connected",
            "description": "A Slack notification that is sent when you successfully connect or reconnect your LinkedIn account.",
            "class": LinkedInConnectionConnected,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_CONNECTION_DISCONNECTED: {
            "name": "LinkedIn Disconnected",
            "description": "A Slack notification that is sent when your LinkedIn account is disconnected from SellScale.",
            "class": LinkedInConnectionDisconnected,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.LINKEDIN_MULTI_THREAD: {
            "name": "Linkedin Multi Thread",
            "description": "A Slack notification that is sent when a Prospect refers you to another person on LinkedIn",
            "class": LinkedInMultiThreadNotification,
            "outbound_channel": "linkedin",
        },
        SlackNotificationType.AI_REPLY_TO_EMAIL: {
            "name": "AI Reply to Email",
            "description": "A Slack notification that is sent when the AI replies to an email",
            "class": EmailAIReplyNotification,
            "outbound_channel": "email",
        },
        SlackNotificationType.EMAIL_LINK_CLICKED: {
            "name": "Email Link Clicked",
            "description": "A Slack notification that is sent when a Prospect clicks a link in an email",
            "class": EmailLinkClickedNotification,
            "outbound_channel": "email",
        },
        SlackNotificationType.EMAIL_PROSPECT_REPLIED: {
            "name": "Email Prospect Replied",
            "description": "A Slack notification that is sent when a Prospect responds to your email",
            "class": EmailProspectRepliedNotification,
            "outbound_channel": "email",
        },
        SlackNotificationType.EMAIL_MULTICHANNELED: {
            "name": "Email Multichannel",
            "description": "A Slack notification that is sent when a Prospect requests a response on email, from a different channel.",
            "class": EmailMultichanneledNotification,
            "outbound_channel": "email",
        },
        SlackNotificationType.EMAIL_NEW_INBOX_CREATED: {
            "name": "New Inbox Created",
            "description": "A Slack notification that is sent whenever a new inbox is created.",
            "class": EmailNewInboxCreatedNotification,
            "outbound_channel": "email",
        },
        SlackNotificationType.DEMO_FEEDBACK_COLLECTED: {
            "name": "Demo Feedback Collected",
            "description": "A Slack notification that is sent whenever you give feedback on a Demo",
            "class": DemoFeedbackCollectedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.DEMO_FEEDBACK_UPDATED: {
            "name": "Demo Feedback Updated",
            "description": "A Slack notification that is sent whenever you give update feedback on a Demo",
            "class": DemoFeedbackUpdatedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.AI_TASK_COMPLETED: {
            "name": "AI Task Completed",
            "description": "A Slack notification that is sent whenever the AI completes a task for you",
            "class": AITaskCompletedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.CAMPAIGN_ACTIVATED: {
            "name": "Campaign Activated",
            "description": "A Slack notification that is sent whenever a campaign is activated",
            "class": CampaignActivatedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.CAMPAIGN_COMPLETED: {
            "name": "Campaign Completed",
            "description": "A Slack notification that is sent whenever a campaign is completed",
            "class": CampaignCompletedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.PROSPECT_ADDED: {
            "name": "Prospect Added",
            "description": "A Slack notification that is sent whenever Prospects are added to your pipeline.",
            "class": ProspectAddedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.PROSPECT_SNOOZED: {
            "name": "Prospect Snoozed",
            "description": "A Slack notification that is sent whenever Prospects are snoozed",
            "class": ProspectSnoozedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.ASSET_CREATED: {
            "name": "Asset Created",
            "description": "A Slack notification that is sent whenever an asset is created.",
            "class": AssetCreatedNotification,
            "outbound_channel": "all",
        },
        SlackNotificationType.PIPELINE_ACTIVITY_DAILY: {
            "name": "Daily Pipeline Activity",
            "description": "A Daily Slack notification that is sent to summarize the activity in your pipeline",
            "class": PipelineActivityDailyNotification,
            "outbound_channel": "all",
        },
    }

    return map_slack_notification_type_to_metadata


class SlackNotification(db.Model):  # type: ignore
    __tablename__ = "slack_notification"

    id = db.Column(db.Integer, primary_key=True)

    notification_type = db.Column(
        db.Enum(SlackNotificationType), nullable=False, unique=True
    )
    notification_name = db.Column(db.String(255), nullable=False)
    notification_description = db.Column(db.String, nullable=False)
    notification_outbound_channel = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "notification_type": self.notification_type.value,
            "notification_name": self.notification_name,
            "notification_description": self.notification_description,
            "notification_outbound_channel": self.notification_outbound_channel,
        }


class SentSlackNotification(db.Model):  # type: ignore
    __tablename__ = "sent_slack_notification"

    id = db.Column(db.Integer, primary_key=True)

    # Who sent the notification
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)

    # What type of notification was sent
    notification_type = db.Column(db.Enum(SlackNotificationType), nullable=False)

    # What was the 'base' message
    message = db.Column(db.String, nullable=False)

    # Which webhook URL was sent to
    webhook_url = db.Column(JSONB, nullable=True)

    # Which channel was the notification sent to
    slack_channel_id = db.Column(db.String(255), nullable=True)

    # What were the Slack notification blocks
    blocks = db.Column(db.ARRAY(JSONB), nullable=True)

    # If there was an error sending the notification, what was it?
    error = db.Column(db.String, nullable=True)


class SlackNotificationClassLogger(db.Model):  # type: ignore
    __tablename__ = "slack_notification_class_logger"

    id = db.Column(db.Integer, primary_key=True)

    # The notification type
    notification_type = db.Column(db.Enum(SlackNotificationType), nullable=False)

    # Arguments passed
    arguments = db.Column(JSONB, nullable=True)

    # Status
    status = db.Column(db.String, nullable=True)

    # Error
    error = db.Column(db.String, nullable=True)


def populate_slack_notifications():
    """Populate the Slack notifications table with all of the Slack notifications. Should be called after introducing a new Slack notification type."""
    for slack_notification_type in SlackNotificationType:
        # Get the Slack notification
        slack_notification = SlackNotification.query.filter_by(
            notification_type=slack_notification_type
        ).first()

        # If the Slack notification doesn't exist, then create it
        if not slack_notification:
            slack_notification = SlackNotification(
                notification_type=slack_notification_type,
                notification_name=slack_notification_type.name(),
                notification_description=slack_notification_type.description(),
                notification_outbound_channel=slack_notification_type.get_outbound_channel(),
            )
            db.session.add(slack_notification)
            db.session.commit()
