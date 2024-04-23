from http import client
from app import db
import enum


class OperatorDashboardEntryPriority(enum.Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    COMPLETED = 10


class OperatorDashboardEntryStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"


class OperatorDashboardTaskType(enum.Enum):
    CONNECT_LINKEDIN = "CONNECT_LINKEDIN"
    LINKEDIN_DISCONNECTED = "LINKEDIN_DISCONNECTED"

    EMAIL_CAMPAIGN_REVIEW = "EMAIL_CAMPAIGN_REVIEW"
    LINKEDIN_CAMPAIGN_REVIEW = "LINKEDIN_CAMPAIGN_REVIEW"
    BOTH_CAMPAIGN_REVIEW = "BOTH_CAMPAIGN_REVIEW"

    DEMO_FEEDBACK_NEEDED = "DEMO_FEEDBACK_NEEDED"
    SCHEDULING_FEEDBACK_NEEDED = "SCHEDULING_FEEDBACK_NEEDED"
    SCHEDULING_NEEDED = "SCHEDULING_NEEDED"

    CAMPAIGN_REQUEST = "CAMPAIGN_REQUEST"

    SEGMENT_CREATION = "SEGMENT_CREATION"
    ENRICH_SEGMENT = "ENRICH_SEGMENT"
    CREATE_PREFILTERS = "CREATE_PREFILTERS"
    REVIEW_SEGMENT = "REVIEW_SEGMENT"

    CONNECT_SLACK = "CONNECT_SLACK"
    ADD_DNC_FILTERS = "ADD_DNC_FILTERS"
    ADD_CALENDAR_LINK = "ADD_CALENDAR_LINK"

    REP_INTERVENTION_NEEDED = "REP_INTERVENTION_NEEDED"

    VOICE_BUILDER = "VOICE_BUILDER"
    REVIEW_AI_BRAIN = "REVIEW_AI_BRAIN"


class OperatorDashboardEntry(db.Model):
    __tablename__ = "operator_dashboard_entry"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    urgency = db.Column(db.Enum(OperatorDashboardEntryPriority), nullable=False)
    tag = db.Column(db.String, nullable=False)
    emoji = db.Column(db.String, nullable=False)
    title = db.Column(db.String, nullable=False)
    subtitle = db.Column(db.String, nullable=False)
    cta = db.Column(db.String, nullable=False)
    cta_url = db.Column(db.String, nullable=False)
    status = db.Column(db.Enum(OperatorDashboardEntryStatus), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    task_type = db.Column(db.Enum(OperatorDashboardTaskType), nullable=False)
    task_data = db.Column(db.JSON, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "urgency": self.urgency.name,
            "tag": self.tag,
            "emoji": self.emoji,
            "title": self.title,
            "subtitle": self.subtitle,
            "cta": self.cta,
            "cta_url": self.cta_url,
            "status": self.status.name,
            "due_date": self.due_date.isoformat(),
            "task_type": self.task_type.name,
            "task_data": self.task_data,
        }
