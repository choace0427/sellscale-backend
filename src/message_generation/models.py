from app import db
import enum


class GeneratedMessageStatus(enum.Enum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    APPROVED = "APPROVED"
    SENT = "SENT"


class GeneratedMessageType(enum.Enum):
    LINKEDIN = "LINKEDIN"
    EMAIL = "EMAIL"


class GeneratedMessageJobStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GeneratedMessage(db.Model):
    __tablename__ = "generated_message"

    id = db.Column(db.Integer, primary_key=True)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    gnlp_model_id = db.Column(db.Integer, db.ForeignKey("gnlp_models.id"))
    research_points = db.Column(db.ARRAY(db.Integer), nullable=False)
    prompt = db.Column(db.String, nullable=False)
    completion = db.Column(db.String, nullable=False)
    message_status = db.Column(db.Enum(GeneratedMessageStatus), nullable=False)
    message_type = db.Column(db.Enum(GeneratedMessageType), nullable=True)
    date_sent = db.Column(db.DateTime, nullable=True)
    batch_id = db.Column(db.String, nullable=True)

    verified_for_send = db.Column(db.Boolean, nullable=True)

    human_edited = db.Column(db.Boolean, nullable=True)

    adversarial_ai_prediction = db.Column(db.Boolean, nullable=True)
    sensitive_content_flag = db.Column(db.Boolean, nullable=True)
    message_cta = db.Column(
        db.Integer, db.ForeignKey("generated_message_cta.id"), nullable=True
    )

    unknown_named_entities = db.Column(db.ARRAY(db.String), nullable=True)
    problems = db.Column(db.ARRAY(db.String), nullable=True)

    good_message = db.Column(db.Boolean, nullable=True)
    few_shot_prompt = db.Column(db.String, nullable=True)
    generated_message_instruction_id = db.Column(
        db.Integer, db.ForeignKey("generated_message_instruction.id"), nullable=True
    )


class GeneratedMessageInstruction(db.Model):
    __tablename__ = "generated_message_instruction"

    id = db.Column(db.Integer, primary_key=True)

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    text_value = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=True)


class GeneratedMessageCTA(db.Model):
    __tablename__ = "generated_message_cta"

    id = db.Column(db.Integer, primary_key=True)

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    text_value = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=True)


class GeneratedMessageFeedback(db.Model):
    __tablename__ = "generated_message_feedback"

    id = db.Column(db.Integer, primary_key=True)

    generated_message_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id"), nullable=False
    )
    feedback_value = db.Column(db.String, nullable=False)


class GeneratedMessageJob(db.Model):
    __tablename__ = "generated_message_job"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    batch_id = db.Column(db.String, nullable=True)

    status = db.Column(db.Enum(GeneratedMessageJobStatus), nullable=False)
