from app import db
import enum
import sqlalchemy as sa
from src.research.models import ResearchPointType


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
    gnlp_model_id = db.Column(
        db.Integer, db.ForeignKey("gnlp_models.id"), nullable=True
    )
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
    highlighted_words = db.Column(db.ARRAY(db.String), nullable=True)

    good_message = db.Column(db.Boolean, nullable=True)
    few_shot_prompt = db.Column(db.String, nullable=True)
    generated_message_instruction_id = db.Column(
        db.Integer, db.ForeignKey("generated_message_instruction.id"), nullable=True
    )

    adversary_identified_mistake = db.Column(db.String, nullable=True)
    adversary_identified_fix = db.Column(db.String, nullable=True)

    stack_ranked_message_generation_configuration_id = db.Column(
        db.Integer,
        db.ForeignKey("stack_ranked_message_generation_configuration.id"),
        nullable=True,
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

    def get_active_ctas_for_archetype(archetype_id):
        return GeneratedMessageCTA.query.filter_by(
            archetype_id=archetype_id, active=True
        ).all()


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


class GeneratedMessageEditRecord(db.Model):
    __tablename__ = "generated_message_edit_record"

    id = db.Column(db.Integer, primary_key=True)
    generated_message_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id"), nullable=False
    )
    original_text = db.Column(db.String, nullable=False)
    edited_text = db.Column(db.String, nullable=False)

    editor_id = db.Column(db.Integer, db.ForeignKey("editor.id"), nullable=True)


class ConfigurationType(enum.Enum):
    STRICT = "STRICT"  # all transformers must be present to use configuration
    DEFAULT = "DEFAULT"  # if no better configuration present, use this configuration. randomly samples from selected transformers.


class StackRankedMessageGenerationConfiguration(db.Model):
    __tablename__ = "stack_ranked_message_generation_configuration"

    id = db.Column(db.Integer, primary_key=True)
    configuration_type = db.Column(db.Enum(ConfigurationType), nullable=False)
    generated_message_type = db.Column(db.Enum(GeneratedMessageType), nullable=False)
    research_point_types = db.Column(
        db.ARRAY(db.String),
        nullable=True,
    )
    generated_message_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    instruction = db.Column(db.String, nullable=False)
    computed_prompt = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=True, default=True)

    name = db.Column(db.String, nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)
    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    priority = db.Column(
        db.Integer, nullable=True
    )  # lower = less priority; higher = more priority

    def to_dict(self):
        return {
            "id": self.id,
            "configuration_type": self.configuration_type.value,
            "generated_message_type": self.generated_message_type.value,
            "research_point_types": self.research_point_types,
            "generated_message_ids": self.generated_message_ids,
            "instruction": self.instruction,
            "computed_prompt": self.computed_prompt,
            "name": self.name,
            "client_id": self.client_id,
            "archetype_id": self.archetype_id,
            "priority": self.priority,
        }
