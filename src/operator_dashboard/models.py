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
        }
