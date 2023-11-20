from app import db
from enum import Enum


class TriggerType(Enum):
    RECURRING_PROSPECT_SCRAPE = "recurring_prospect_scrape"
    NEWS_EVENT = "news_event"


class Trigger(db.Model):
    __tablename__ = "trigger"

    id = db.Column(db.Integer, primary_key=True)

    emoji = db.Column(db.String, nullable=False, default="⚡️")
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)

    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    interval_in_minutes = db.Column(db.Integer, nullable=True)

    trigger_type = db.Column(db.Enum(TriggerType), nullable=False)
    trigger_config = db.Column(db.JSON, nullable=False, default={})

    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    active = db.Column(db.Boolean, nullable=False, default=True)
