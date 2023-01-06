from email.policy import default
from app import db
import sqlalchemy as sa
import enum


class PhantomBusterType(enum.Enum):
    INBOX_SCRAPER = "INBOX_SCRAPER"
    OUTBOUND_ENGINE = "OUTBOUND_ENGINE"


class PhantomBusterConfig(db.Model):
    __tablename__ = "phantom_buster_config"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    pb_type = db.Column(db.Enum(PhantomBusterType), nullable=True)

    google_sheets_uuid = db.Column(db.String, nullable=True)

    phantom_name = db.Column(db.String)
    phantom_uuid = db.Column(db.String)

    last_run_date = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String, nullable=True)
