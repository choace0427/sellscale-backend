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


class TriggerRun(db.Model):
    __tablename__ = "trigger_run"

    id = db.Column(db.Integer, primary_key=True)

    trigger_id = db.Column(db.Integer, db.ForeignKey("trigger.id"), nullable=False)
    trigger = db.relationship("Trigger", backref="trigger_runs")

    run_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    run_status = db.Column(db.String, nullable=False)
    run_message = db.Column(db.String, nullable=True)

    def to_dict(self):
        prospects_found = TriggerProspect.query.filter_by(trigger_run_id=self.id).all()

        return {
            "id": self.id,
            "trigger_id": self.trigger_id,
            "run_at": self.run_at,
            "run_status": self.run_status,
            "run_message": self.run_message,
            "num_prospects": len(prospects_found),
            "companies": list(set([prospect.company for prospect in prospects_found])),
        }


class TriggerProspect(db.Model):
    __tablename__ = "trigger_prospect"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    company = db.Column(db.String, nullable=True)
    linkedin_url = db.Column(db.String, nullable=True)
    custom_data = db.Column(db.String, nullable=True)

    trigger_run_id = db.Column(
        db.Integer, db.ForeignKey("trigger_run.id"), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "title": self.title,
            "company": self.company,
            "linkedin_url": self.linkedin_url,
            "custom_data": self.custom_data,
        }
