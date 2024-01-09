from app import db
from src.message_generation.models import GeneratedMessageType

import enum

EDITING_COST_PER_PROSPECT = 0.132
UPWORKER_RECEIPT_LINK = "https://www.upwork.com/nx/payments/reports/transaction-history"


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
    canonical_name = db.Column(db.String(255), nullable=True)
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

    receipt_link = db.Column(db.String, nullable=True)
    cost = db.Column(db.Float, nullable=True)

    priority_rating = db.Column(db.Integer, nullable=True, default=0)
    is_daily_generation = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "canonical_name": self.canonical_name,
            "prospect_ids": self.prospect_ids,
            "campaign_type": self.campaign_type.value,
            "ctas": self.ctas,
            "client_archetype_id": self.client_archetype_id,
            "client_sdr_id": self.client_sdr_id,
            "campaign_start_date": self.campaign_start_date,
            "campaign_end_date": self.campaign_end_date,
            "status": self.status.value,
            "uuid": self.uuid,
            "receipt_link": self.receipt_link,
            "cost": self.cost,
            "priority_rating": self.priority_rating,
            "is_daily_generation": self.is_daily_generation,
        }

    def calculate_cost(self) -> float:
        cost = EDITING_COST_PER_PROSPECT * len(self.prospect_ids)
        self.cost = cost
        self.receipt_link = UPWORKER_RECEIPT_LINK
        return EDITING_COST_PER_PROSPECT * len(self.prospect_ids)
