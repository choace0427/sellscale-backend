import enum
from typing import Optional
from app import db
import sqlalchemy as sa


class EmailType(enum.Enum):
    ANCHOR = "ANCHOR"
    SELLSCALE = "SELLSCALE"
    ALIAS = "ALIAS"


class SDREmailBank(db.Model):
    __tablename__ = "sdr_email_bank"

    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    # Email
    email_address = db.Column(db.String, nullable=False, unique=True)
    email_type = db.Column(db.Enum(EmailType), nullable=False)

    # Client SDR
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )

    # Domain
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=True)

    # Nylas Connection
    nylas_auth_code = db.Column(db.String, nullable=True)
    nylas_account_id = db.Column(db.String, nullable=True)
    nylas_active = db.Column(db.Boolean, nullable=True, default=False)

    # AWS Connection
    aws_workmail_user_id = db.Column(db.String, nullable=True)
    aws_username = db.Column(db.String, nullable=True)
    aws_password = db.Column(
        db.String, nullable=True
    )  # This needs to be removed in the future, storing for now.

    # Smartlead Connection
    smartlead_account_id = db.Column(db.Integer, nullable=True)
    smartlead_warmup_enabled = db.Column(db.Boolean, nullable=True, default=False)
    smartlead_reputation = db.Column(db.Float, nullable=True)

    # TODO: Eventually we need to bring warmup information into this table from the WarmupSnapshot table.
    total_sent_count = db.Column(db.Integer, nullable=True)
    previous_total_sent_count = db.Column(db.Integer, nullable=True)
    daily_sent_count = db.Column(db.Integer, nullable=True)
    daily_limit = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        # Get the attached Send Schedule
        send_schedule: SDREmailSendSchedule = SDREmailSendSchedule.query.filter(
            SDREmailSendSchedule.email_bank_id == self.id
        ).first()

        # DO NOT EXPOSE PASSWORDS
        return {
            "id": self.id,
            "active": self.active,
            "email_address": self.email_address,
            "email_type": self.email_type.value,
            "client_sdr_id": self.client_sdr_id,
            "domain_id": self.domain_id,
            "nylas_auth_code": self.nylas_auth_code,
            "nylas_account_id": self.nylas_account_id,
            "nylas_active": self.nylas_active,
            "send_schedule": send_schedule.to_dict() if send_schedule else None,
            "aws_workmail_user_id": self.aws_workmail_user_id,
            "aws_username": self.aws_username,
            "smartlead_account_id": self.smartlead_account_id,
            "smartlead_warmup_enabled": self.smartlead_warmup_enabled,
            "smartlead_reputation": self.smartlead_reputation,
            "total_sent_count": self.total_sent_count,
            "previous_total_sent_count": self.previous_total_sent_count,
            "daily_sent_count": self.daily_sent_count,
            "daily_limit": self.daily_limit,
        }


class SDREmailSendSchedule(db.Model):
    __tablename__ = "sdr_email_send_schedule"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    email_bank_id = db.Column(
        db.Integer, db.ForeignKey("sdr_email_bank.id"), nullable=False
    )

    # Times to send email
    time_zone = db.Column(db.String, nullable=False)
    days = db.Column(db.ARRAY(db.Integer), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "email_bank_id": self.email_bank_id,
            "time_zone": self.time_zone,
            "days": self.days,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
        }
