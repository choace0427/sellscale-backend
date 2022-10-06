from app import db
import enum


class GeneratedMessageStatus(enum.Enum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    APPROVED = "APPROVED"
    SENT = "SENT"


class GeneratedMessage(db.Model):
    __tablename__ = "generated_message"

    id = db.Column(db.Integer, primary_key=True)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    gnlp_model_id = db.Column(db.Integer, db.ForeignKey("gnlp_models.id"))
    research_points = db.Column(db.ARRAY(db.Integer), nullable=False)
    prompt = db.Column(db.String, nullable=False)
    completion = db.Column(db.String, nullable=False)
    message_status = db.Column(db.Enum(GeneratedMessageStatus), nullable=False)
    date_sent = db.Column(db.DateTime, nullable=True)
