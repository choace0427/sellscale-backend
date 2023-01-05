from app import db
from src.prospecting.models import ProspectStatus
from src.research.models import ResearchPointType
import sqlalchemy as sa


class Client(db.Model):
    __tablename__ = "client"

    id = db.Column(db.Integer, primary_key=True)

    company = db.Column(db.String)
    contact_name = db.Column(db.String)
    contact_email = db.Column(db.String)

    active = db.Column(db.Boolean, nullable=True)

    pipeline_notifications_webhook_url = db.Column(db.String, nullable=True)

    notification_allowlist = db.Column(
        db.ARRAY(sa.Enum(ProspectStatus, create_constraint=False)),
        nullable=True,
    )

    linkedin_outbound_enabled = db.Column(db.Boolean, nullable=True)
    email_outbound_enabled = db.Column(db.Boolean, nullable=True)

    super_sight_link = db.Column(db.String, nullable=True)


class ClientArchetype(db.Model):
    __tablename__ = "client_archetype"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    archetype = db.Column(db.String)
    filters = db.Column(db.JSON, nullable=True)

    active = db.Column(db.Boolean, nullable=True, default=True)

    transformer_blocklist = db.Column(
        db.ARRAY(sa.Enum(ResearchPointType, create_constraint=False)),
        nullable=True,
    )  # use this list to blocklist transformer durings message generation

    disable_ai_after_prospect_engaged = db.Column(
        db.Boolean, nullable=True, default=False
    )

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)


class ClientSDR(db.Model):
    __tablename__ = "client_sdr"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    name = db.Column(db.String)
    email = db.Column(db.String)

    weekly_li_outbound_target = db.Column(db.Integer, nullable=True)
    weekly_email_outbound_target = db.Column(db.Integer, nullable=True)
    scheduling_link = db.Column(db.String, nullable=True)

    auth_token = db.Column(db.String, nullable=True)

    pipeline_notifications_webhook_url = db.Column(db.String, nullable=True)
    notification_allowlist = db.Column(
        db.ARRAY(sa.Enum(ProspectStatus, create_constraint=False)),
        nullable=True,
    )

    manual_warning_message = db.Column(db.String, nullable=True)
