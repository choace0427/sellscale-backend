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
    monthly_revenue = db.Column(db.Integer, nullable=True)
    seat_expansion_opportunity = db.Column(db.Integer, nullable=True)


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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "archetype": self.archetype,
            "filters": self.filters,
            "active": self.active,
            "transformer_blocklist": [t.value for t in self.transformer_blocklist],
            "disable_ai_after_prospect_engaged": self.disable_ai_after_prospect_engaged,
            "client_sdr_id": self.client_sdr_id,
        }


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

    li_at_token = db.Column(db.String)
    last_li_conversation_scrape_date = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        client: Client = Client.query.get(self.client_id)

        return {
            "client_name": client.company,
            "sdr_name": self.name,
            "sdr_email": self.email,
            "weekly_li_outbound_target": self.weekly_li_outbound_target,
            "weekly_email_outbound_target": self.weekly_email_outbound_target,
            "scheduling_link": self.scheduling_link,
            "last_li_conversation_scrape_date": self.last_li_conversation_scrape_date,
        }
