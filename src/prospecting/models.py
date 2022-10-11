from app import db
import enum


class ProspectStatus(enum.Enum):
    PROSPECTED = "PROSPECTED"

    NOT_QUALIFIED = "NOT_QUALIFIED"
    SENT_OUTREACH = "SENT_OUTREACH"

    ACCEPTED = "ACCEPTED"
    RESPONDED = "RESPONDED"
    ACTIVE_CONVO = "ACTIVE_CONVO"

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


class ProspectStatusRecords(db.Model):
    __tablename__ = "prospect_status_records"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    from_status = db.Column(db.Enum(ProspectStatus), nullable=True)
    to_status = db.Column(db.Enum(ProspectStatus), nullable=True)


# map of to_status and from status
# ensure that the prospect's from_status is in the array of the value of
#   "to_status" index
VALID_FROM_STATUSES_MAP = {
    ProspectStatus.PROSPECTED: [],
    ProspectStatus.NOT_QUALIFIED: [ProspectStatus.PROSPECTED],
    ProspectStatus.SENT_OUTREACH: [ProspectStatus.PROSPECTED],
    ProspectStatus.ACCEPTED: [ProspectStatus.SENT_OUTREACH],
    ProspectStatus.RESPONDED: [ProspectStatus.ACCEPTED],
    ProspectStatus.ACTIVE_CONVO: [ProspectStatus.RESPONDED],
    ProspectStatus.NOT_INTERESTED: [
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
    ],
    ProspectStatus.DEMO_SET: [ProspectStatus.RESPONDED, ProspectStatus.ACTIVE_CONVO],
    ProspectStatus.DEMO_WON: [ProspectStatus.DEMO_SET],
    ProspectStatus.DEMO_LOSS: [ProspectStatus.DEMO_SET],
}
