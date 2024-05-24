import enum
from app import db
from src.prospecting.models import ProspectChannels


class NotificationStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class NotificationType(enum.Enum):
    UNKNOWN = "UNKNOWN"
    UNREAD_MESSAGE = "UNREAD_MESSAGE"
    NEEDS_BUMP = "NEEDS_BUMP"
    SCHEDULING = "SCHEDULING"


class DailyNotification(db.Model):
    __tablename__ = "daily_notifications"

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), primary_key=True
    )
    prospect_id = db.Column(
        db.Integer, db.ForeignKey("prospect.id"), primary_key=True, default=-1
    )
    type = db.Column(
        db.Enum(NotificationType), primary_key=True, default=NotificationType.UNKNOWN
    )

    status = db.Column(db.Enum(NotificationStatus), nullable=False)

    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)

    __table_args__ = (db.PrimaryKeyConstraint("client_sdr_id", "prospect_id", "type"),)

    def to_dict(self):
        return {
            "client_sdr_id": self.client_sdr_id,
            "prospect_id": self.prospect_id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "due_date": self.due_date.isoformat(),
        }


class EngagementFeedType(enum.Enum):
    UNKNOWN = "unknown"
    ACCEPTED_INVITE = "ACCEPTED_INVITE"
    RESPONDED = "RESPONDED"
    SCHEDULING = "SCHEDULING"
    EMAIL_OPENED = "EMAIL_OPENED"
    EMAIL_LINK_CLICKED = "EMAIL_LINK_CLICKED"
    SET_TIME_TO_DEMO = "SET_TIME_TO_DEMO"


class EngagementFeedItem(db.Model):
    __tablename__ = "engagement_feed_items"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    channel_type = db.Column(db.Enum(ProspectChannels), nullable=False)
    engagement_type = db.Column(db.Enum(EngagementFeedType), nullable=False)

    viewed = db.Column(db.Boolean, nullable=False, default=False)
    engagement_metadata = db.Column(db.JSON, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": str(self.created_at),
            "client_sdr_id": self.client_sdr_id,
            "prospect_id": self.prospect_id,
            "channel_type": self.channel_type.value,
            "engagement_type": self.engagement_type.value,
            "viewed": self.viewed,
            "engagement_metadata": self.parse_iscraper_metadata(
                self.engagement_metadata
            ),
        }

    def parse_iscraper_metadata(self, metadata: dict) -> dict:
        """Parses metadata from iScraper.

        Args:
            metadata (dict): Metadata

        Returns:
            dict: Parsed metadata that is SellScale controlled
        """
        ss_controlled_metadata = {}
        if metadata is None:
            return ss_controlled_metadata

        ss_controlled_metadata["li_thread_url"] = metadata.get("threadUrl")
        ss_controlled_metadata["message"] = metadata.get("message")
        ss_controlled_metadata["sender_first_name"] = metadata.get("firstnameFrom")
        ss_controlled_metadata["sender_last_name"] = metadata.get("lastnameFrom")
        ss_controlled_metadata["read"] = metadata.get("readStatus")
        ss_controlled_metadata["last_message_timestamp"] = metadata.get(
            "lastMessageDate"
        )
        ss_controlled_metadata["last_message_from_me"] = metadata.get(
            "isLastMessageFromMe"
        )

        return ss_controlled_metadata
