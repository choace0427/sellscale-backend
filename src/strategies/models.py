from app import db
from enum import Enum
from typing import TypedDict

class StrategyStatuses(Enum):
    FAILED = "FAILED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"


class Strategies(db.Model):
    __tablename__ = "stragegies"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    tagged_campaigns = db.Column(db.String, nullable=True)
    status = db.Column(db.Enum(StrategyStatuses), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)

    def to_dict(self, deep_get: bool = False):
        retval = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tagged_campaigns": self.tagged_campaigns,
            "status": self.status.value,
            "client_id": self.client_id,
            "created_by": self.created_by,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }

        if deep_get:
            client_archetype_mappings = StrategyClientArchetypeMapping.query.filter_by(strategy_id=self.id).all()
            retval["client_archetype_mappings"] = [mapping.to_dict(deep_get=True) for mapping in client_archetype_mappings]

        return retval

class StrategyClientArchetypeMapping(db.Model):
    __tablename__ = "strategy_client_archetype_mapping"

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(db.Integer, db.ForeignKey("stragegies.id"), nullable=False)
    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"), nullable=False)

    def to_dict(self, deep_get: bool = False):
        retval = {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "client_archetype_id": self.client_archetype_id,
        }

        if deep_get:
            from model_import import ClientArchetype, ClientSDR

            retval["strategy"] = Strategies.query.get(self.strategy_id).to_dict()
            retval["client_archetype"] = ClientArchetype.query.get(self.client_archetype_id).to_dict()

        return retval