from db import db
import enum


class ProspectStatus(enum.Enum):
    PROSPECTED = "PROSPECTED"

    NOT_QUALIFIED = "NOT_QUALIFIED"
    SENT_OUTREACH = "SENT_OUTREACH"

    RESPONDED = "RESPONDED"
    NOT_INTERESTED = "NOT_INTERESTED"

    DEMO_SET = "DEMO_SET"

    DEMO_WON = "DEMO_WON"
    DEMO_LOSS = "DEMO_LOSS"


class Prospect(db.Model):
    __tablename__ = "prospect"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))

    company = db.Column(db.String, nullable=True)
    company_url = db.Column(db.String, nullable=True)
    employee_count = db.Column(db.String, nullable=True)
    full_name = db.Column(db.String, nullable=True)
    industry = db.Column(db.String, nullable=True)
    linkedin_url = db.Column(db.String, nullable=True)
    linkedin_bio = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    twitter_url = db.Column(db.String, nullable=True)

    batch = db.Column(db.String, nullable=True)
    status = db.Column(db.Enum(ProspectStatus), nullable=True)

    approved_outreach_message_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")
    )
