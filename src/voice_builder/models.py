from app import db
import sqlalchemy as sa, enum
from model_import import GeneratedMessageType


class VoiceBuilderOnboarding(db.Model):
    __tablename__ = "voice_builder_onboarding"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    generated_message_type = db.Column(db.Enum(GeneratedMessageType), nullable=False)
    stack_ranked_message_generation_configuration_id = db.Column(
        db.Integer,
        db.ForeignKey("stack_ranked_message_generation_configuration.id"),
        nullable=True,
    )

    sample_prompt_1 = db.Column(db.String, nullable=True)
    sample_completion_1 = db.Column(db.String, nullable=True)

    sample_prompt_2 = db.Column(db.String, nullable=True)
    sample_completion_2 = db.Column(db.String, nullable=True)

    sample_prompt_3 = db.Column(db.String, nullable=True)
    sample_completion_3 = db.Column(db.String, nullable=True)

    sample_prompt_4 = db.Column(db.String, nullable=True)
    sample_completion_4 = db.Column(db.String, nullable=True)

    sample_prompt_5 = db.Column(db.String, nullable=True)
    sample_completion_5 = db.Column(db.String, nullable=True)
