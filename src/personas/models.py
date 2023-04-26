from app import db
import sqlalchemy as sa, enum


class PersonaSplitRequestTaskStatus(enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PersonaSplitRequest(db.Model):
    __tablename__ = "persona_split_request"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    source_client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id")
    )
    destination_client_archetype_ids = db.Column(db.ARRAY(db.Integer))


class PersonaSplitRequestTask(db.Model):
    __tablename__ = "persona_split_request_task"

    id = db.Column(db.Integer, primary_key=True)
    persona_split_request_id = db.Column(
        db.Integer, db.ForeignKey("persona_split_request.id")
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    destination_client_archetype_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    status = db.Column(sa.Enum(PersonaSplitRequestTaskStatus, create_constraint=False))
    tries = db.Column(db.Integer, default=0)
