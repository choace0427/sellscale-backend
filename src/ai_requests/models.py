from app import db
import enum


class AIRequestStatus(enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIRequest(db.Model):
    __tablename__ = "ai_request"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )

    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    percent_complete = db.Column(db.Integer, nullable=False)
    creation_date = db.Column(db.DateTime, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(AIRequestStatus), nullable=False)
    message = db.Column(db.String, nullable=True)
