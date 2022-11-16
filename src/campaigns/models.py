from app import db
from src.message_generation.services import GeneratedMessageType

import enum


class OutboundCampaignStatus(enum.Enum):
    PENDING = "PENDING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class OutboundCampaign(db.Model):
    __tablename__ = "outbound_campaign"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    prospect_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    campaign_type = db.Column(db.Enum(GeneratedMessageType), nullable=False)
    ctas = db.Column(db.ARRAY(db.Integer), nullable=True)
    email_schema_id = db.Column(
        db.Integer, db.ForeignKey("email_schema.id"), nullable=True
    )
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    campaign_start_date = db.Column(db.DateTime, nullable=False)
    campaign_end_date = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.Enum(OutboundCampaignStatus), nullable=False)
