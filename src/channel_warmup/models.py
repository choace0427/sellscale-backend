from email.policy import default
from typing import Optional

from app import db

from src.prospecting.models import ProspectChannels
from sqlalchemy.dialects import postgresql


class ChannelWarmup(db.Model):
    __tablename__ = "channel_warmup"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    channel_type = db.Column(
        postgresql.ENUM(ProspectChannels, name="prospectchannels", create_type=False),
        nullable=False,
    )

    daily_sent_count = db.Column(db.Integer, nullable=False)
    daily_limit = db.Column(db.Integer, nullable=False)

    warmup_enabled = db.Column(db.Boolean, nullable=False, default=False)
    reputation = db.Column(db.Float, nullable=True)
