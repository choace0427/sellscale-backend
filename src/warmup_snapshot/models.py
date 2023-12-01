from email.policy import default
from typing import Optional

from app import db

from src.prospecting.models import ProspectChannels
from sqlalchemy.dialects import postgresql


class WarmupSnapshot(db.Model):
    __tablename__ = "warmup_snapshot"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    channel_type = db.Column(
        postgresql.ENUM(ProspectChannels, name="prospectchannels", create_type=False),
        nullable=False,
    )

    account_name = db.Column(db.String, nullable=True)

    total_sent_count = db.Column(db.Integer, nullable=True)
    previous_total_sent_count = db.Column(db.Integer, nullable=True)
    daily_sent_count = db.Column(db.Integer, nullable=False)
    daily_limit = db.Column(db.Integer, nullable=False)

    warmup_enabled = db.Column(db.Boolean, nullable=False, default=False)
    reputation = db.Column(db.Float, nullable=True)

    dmarc_record = db.Column(db.String, nullable=True)
    dmarc_record_valid = db.Column(db.Boolean, nullable=True)
    spf_record = db.Column(db.String, nullable=True)
    spf_record_valid = db.Column(db.Boolean, nullable=True)
    dkim_record = db.Column(db.String, nullable=True)
    dkim_record_valid = db.Column(db.Boolean, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "channel_type": self.channel_type.value,
            "account_name": self.account_name,
            "total_sent_count": self.total_sent_count,
            "previous_total_sent_count": self.previous_total_sent_count,
            "daily_sent_count": self.daily_sent_count,
            "daily_limit": self.daily_limit,
            "warmup_enabled": self.warmup_enabled,
            "reputation": self.reputation,
            "dmarc_record": self.dmarc_record,
            "dmarc_record_valid": self.dmarc_record_valid,
            "spf_record": self.spf_record,
            "spf_record_valid": self.spf_record_valid,
            "dkim_record": self.dkim_record,
            "dkim_record_valid": self.dkim_record_valid,
        }
