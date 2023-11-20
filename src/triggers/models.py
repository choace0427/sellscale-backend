from app import db
from enum import Enum

from src.client.models import ClientArchetype


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

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self, include_rich_info: bool = False):
        retval = {
            "id": self.id,
            "emoji": self.emoji,
            "name": self.name,
            "description": self.description,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "interval_in_minutes": self.interval_in_minutes,
            "trigger_type": self.trigger_type.value,
            "trigger_config": self.trigger_config,
            "client_archetype_id": self.client_archetype_id,
            "active": self.active,
        }

        if include_rich_info:
            archetype: ClientArchetype = ClientArchetype.query.get(
                self.client_archetype_id
            )
            if archetype:
                retval["client_archetype"] = archetype.to_dict()

        return retval
