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

    account_name = db.Column(db.String, nullable=True)

    daily_sent_count = db.Column(db.Integer, nullable=False)
    daily_limit = db.Column(db.Integer, nullable=False)

    warmup_enabled = db.Column(db.Boolean, nullable=False, default=False)
    reputation = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "channel_type": self.channel_type.value,
            "account_name": self.account_name,
            "daily_sent_count": self.daily_sent_count,
            "daily_limit": self.daily_limit,
            "warmup_enabled": self.warmup_enabled,
            "reputation": self.reputation,
        }

class ClientWarmup(db.Model):
    __tablename__ = "client_warmup"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))

    date = db.Column(db.Date, nullable=False)

    linkedin_warmup_volume = db.Column(db.Integer, nullable=False, default=False)
    email_warmup_volume = db.Column(db.Integer, nullable=False, default=False)
    total_warmup_volume = db.Column(db.Integer, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "linkedin_warmup": self.linkedin_warmup,
            "email_warmup": self.email_warmup,
            "total_warmup": self.total_warmup,
        }