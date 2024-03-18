from app import db
import enum
from sqlalchemy.dialects.postgresql import JSONB


class OutboundQuotaSnapshot(db.Model):
    __tablename__ = "outbound_quota_snapshot"

    id = db.Column(db.Integer, primary_key=True)

    # Date of the snapshot (unique)
    date = db.Column(db.Date, nullable=False, unique=True)

    # Topline metrics for how many initial messages can / should be sent on a given day
    total_linkedin_quota = db.Column(db.Integer, nullable=False)
    total_email_quota = db.Column(db.Integer, nullable=False)

    # Metadata used to store additional information about the snapshot
    meta_data = db.Column(JSONB, nullable=False)
