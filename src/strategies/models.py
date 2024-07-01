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

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)
