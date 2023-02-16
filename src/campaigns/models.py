from app import db
from src.message_generation.models import GeneratedMessageType

import enum


class OutboundCampaignStatus(enum.Enum):
    PENDING = "PENDING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    IN_PROGRESS = "IN_PROGRESS"
    INITIAL_EDIT_COMPLETE = "INITIAL_EDIT_COMPLETE"
    READY_TO_SEND = "READY_TO_SEND"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"

    def all_statuses():
        return [
            OutboundCampaignStatus.PENDING,
            OutboundCampaignStatus.NEEDS_REVIEW,
            OutboundCampaignStatus.IN_PROGRESS,
            OutboundCampaignStatus.INITIAL_EDIT_COMPLETE,
            OutboundCampaignStatus.READY_TO_SEND,
            OutboundCampaignStatus.COMPLETE,
            OutboundCampaignStatus.CANCELLED,
        ]


class OutboundCampaign(db.Model):
    __tablename__ = "outbound_campaign"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    prospect_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    campaign_type = db.Column(db.Enum(GeneratedMessageType), nullable=False)
    ctas = db.Column(db.ARRAY(db.Integer), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    campaign_start_date = db.Column(db.DateTime, nullable=False)
    campaign_end_date = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.Enum(OutboundCampaignStatus), nullable=False)

    uuid = db.Column(db.String(255), nullable=True)

    editor_id = db.Column(db.Integer, db.ForeignKey("editor.id"), nullable=True)
    reported_time_in_hours = db.Column(db.Float, nullable=True)
    reviewed_feedback = db.Column(db.Boolean, nullable=True)
    sellscale_grade = db.Column(db.String(255), nullable=True)
    brief_feedback_summary = db.Column(db.String, nullable=True)
    detailed_feedback_link = db.Column(db.String, nullable=True)

    editing_due_date = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prospect_ids": self.prospect_ids,
            "campaign_type": self.campaign_type.value,
            "ctas": self.ctas,
            "client_archetype_id": self.client_archetype_id,
            "client_sdr_id": self.client_sdr_id,
            "campaign_start_date": self.campaign_start_date,
            "campaign_end_date": self.campaign_end_date,
            "status": self.status.value,
            "uuid": self.uuid,
        }
