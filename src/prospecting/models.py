from app import db
import enum


class ProspectStatus(enum.Enum):
    PROSPECTED = "PROSPECTED"

    NOT_QUALIFIED = "NOT_QUALIFIED"
    SENT_OUTREACH = "SENT_OUTREACH"

    ACCEPTED = "ACCEPTED"
    RESPONDED = "RESPONDED"  # responded / followed up
    ACTIVE_CONVO = "ACTIVE_CONVO"
    SCHEDULING = "SCHEDULING"

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

    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    full_name = db.Column(db.String, nullable=True)

    industry = db.Column(db.String, nullable=True)

    linkedin_url = db.Column(db.String, nullable=True)
    linkedin_bio = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    last_position = db.Column(db.String, nullable=True)

    twitter_url = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True)

    batch = db.Column(db.String, nullable=True)
    status = db.Column(db.Enum(ProspectStatus), nullable=True)

    approved_outreach_message_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")  # approved linkedin message
    )
    approved_prospect_email_id = db.Column(
        db.Integer, db.ForeignKey("prospect_email.id")  # approved prospect email id
    )

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    li_conversation_thread_id = db.Column(db.String, nullable=True)
    li_last_message_timestamp = db.Column(db.DateTime, nullable=True)
    li_is_last_message_from_sdr = db.Column(db.Boolean, nullable=True)
    li_last_message_from_prospect = db.Column(db.String, nullable=True)

    last_reviewed = db.Column(db.DateTime, nullable=True)
    times_bumped = db.Column(db.Integer, nullable=True)

    deactivate_ai_engagement = db.Column(db.Boolean, nullable=True)

    is_lead = db.Column(db.Boolean, nullable=True)

    def get_by_id(prospect_id: int):
        return Prospect.query.filter_by(id=prospect_id).first()


class ProspectUploadBatch(db.Model):
    __tablename__ = "prospect_upload_batch"

    id = db.Column(db.Integer, primary_key=True)
    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    batch_id = db.Column(db.String, nullable=False)
    num_prospects = db.Column(db.Integer, nullable=False)


class ProspectStatusRecords(db.Model):
    __tablename__ = "prospect_status_records"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    from_status = db.Column(db.Enum(ProspectStatus), nullable=True)
    to_status = db.Column(db.Enum(ProspectStatus), nullable=True)


class ProspectNote(db.Model):
    __tablename__ = "prospect_note"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    note = db.Column(db.String, nullable=False)

    def get_prospect_notes(prospect_id: int):
        return (
            ProspectNote.query.filter(ProspectNote.prospect_id == prospect_id)
            .order_by(ProspectNote.created_at.desc())
            .all()
        )

    def to_dict(self):
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "note": self.note,
        }


# map of to_status and from status
# ensure that the prospect's from_status is in the array of the value of
#   "to_status" index
VALID_FROM_STATUSES_MAP = {
    ProspectStatus.PROSPECTED: [],
    ProspectStatus.NOT_QUALIFIED: [
        ProspectStatus.PROSPECTED,
        ProspectStatus.SENT_OUTREACH,
        ProspectStatus.ACCEPTED,
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.SENT_OUTREACH: [
        ProspectStatus.PROSPECTED,
    ],
    ProspectStatus.ACCEPTED: [ProspectStatus.SENT_OUTREACH],
    ProspectStatus.RESPONDED: [ProspectStatus.ACCEPTED],
    ProspectStatus.ACTIVE_CONVO: [
        ProspectStatus.RESPONDED,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.SCHEDULING: [
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.NOT_INTERESTED: [
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
    ],
    ProspectStatus.DEMO_SET: [
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.DEMO_WON: [ProspectStatus.DEMO_SET],
    ProspectStatus.DEMO_LOSS: [ProspectStatus.DEMO_SET],
}
