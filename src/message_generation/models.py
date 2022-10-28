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
    batch_id = db.Column(db.String, nullable=True)

    human_edited = db.Column(db.Boolean, nullable=True)

    adversarial_ai_prediction = db.Column(db.Boolean, nullable=True)
    sensitive_content_flag = db.Column(db.Boolean, nullable=True)
    message_cta = db.Column(
        db.Integer, db.ForeignKey("generated_message_cta.id"), nullable=True
    )


class GeneratedMessageCTA(db.Model):
    __tablename__ = "generated_message_cta"

    id = db.Column(db.Integer, primary_key=True)

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    text_value = db.Column(db.String, nullable=False)
