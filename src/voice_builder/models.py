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
    instruction = db.Column(db.String, nullable=True)


class VoiceBuilderSamples(db.Model):
    __tablename__ = "voice_builder_samples"

    id = db.Column(db.Integer, primary_key=True)
    voice_builder_onboarding_id = db.Column(
        db.Integer, db.ForeignKey("voice_builder_onboarding.id")
    )

    sample_readable_data = db.Column(db.String, nullable=True)
    sample_prompt = db.Column(db.String, nullable=True)
    sample_completion = db.Column(db.String, nullable=True)

    research_point_ids = db.Column(db.ARRAY(db.Integer), nullable=True)
    cta_id = db.Column(db.Integer, nullable=True)
