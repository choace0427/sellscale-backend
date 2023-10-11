import enum
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
    email_address = db.Column(db.String, nullable=False, unique=True)
    email_type = db.Column(db.Enum(EmailType), nullable=False)

    # Client SDR
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )

    # Nylas Connection
    nylas_auth_code = db.Column(db.String, nullable=True)
    nylas_account_id = db.Column(db.String, nullable=True)
    nylas_active = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self) -> dict:
        # Get the attached Send Schedule
        send_schedule: SDREmailSendSchedule = SDREmailSendSchedule.query.filter(
            SDREmailSendSchedule.email_bank_id == self.id
        ).first()

        return {
            "id": self.id,
            "active": self.active,
            "email_address": self.email_address,
            "email_type": self.email_type.value,
            "client_sdr_id": self.client_sdr_id,
            "nylas_auth_code": self.nylas_auth_code,
            "nylas_account_id": self.nylas_account_id,
            "nylas_active": self.nylas_active,
            "send_schedule": send_schedule.to_dict() if send_schedule else None,
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
