from app import db
import sqlalchemy as sa, enum
from model_import import GeneratedMessageType, ResearchPoints


class VoiceBuilderOnboarding(db.Model):
    __tablename__ = "voice_builder_onboarding"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    generated_message_type = db.Column(db.Enum(GeneratedMessageType), nullable=False)
    stack_ranked_message_generation_configuration_id = db.Column(
        db.Integer,
        db.ForeignKey("stack_ranked_message_generation_configuration.id"),
        nullable=True,
    )
    instruction = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_archetype_id": self.client_archetype_id,
            "generated_message_type": self.generated_message_type.value,
            "stack_ranked_message_generation_configuration_id": self.stack_ranked_message_generation_configuration_id,
            "instruction": self.instruction,
            "created_at": str(self.created_at),
        }


class VoiceBuilderSamples(db.Model):
    __tablename__ = "voice_builder_samples"

    id = db.Column(db.Integer, primary_key=True)
    voice_builder_onboarding_id = db.Column(
        db.Integer, db.ForeignKey("voice_builder_onboarding.id")
    )

    sample_readable_data = db.Column(db.String, nullable=True)
    sample_prompt = db.Column(db.String, nullable=True)
    sample_final_prompt = db.Column(db.String, nullable=True)
    sample_completion = db.Column(db.String, nullable=True)
    sample_problems = db.Column(db.ARRAY(db.String), nullable=True)
    sample_highlighted_words = db.Column(db.ARRAY(db.String), nullable=True)

    research_point_ids = db.Column(db.ARRAY(db.Integer), nullable=True)
    cta_id = db.Column(db.Integer, nullable=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=True)

    def to_dict(self):

        from src.prospecting.models import Prospect
        from src.message_generation.models import GeneratedMessageCTA

        if self.prospect_id:
            prospect = Prospect.query.get(self.prospect_id)
        else:
            prospect = None

        # Get meta_data
        research_points: list[ResearchPoints] = ResearchPoints.query.filter(
            ResearchPoints.id.in_(self.research_point_ids)
        ).all()
        cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(self.cta_id)

        return {
            "id": self.id,
            "voice_builder_onboarding_id": self.voice_builder_onboarding_id,
            "sample_readable_data": self.sample_readable_data,
            "sample_prompt": self.sample_prompt,
            "sample_final_prompt": self.sample_final_prompt,
            "sample_completion": self.sample_completion,
            "sample_problems": self.sample_problems,
            "sample_highlighted_words": self.sample_highlighted_words,
            "research_point_ids": self.research_point_ids,
            "research_point_types": [
                rp.research_point_type.value
                for rp in ResearchPoints.query.filter(
                    ResearchPoints.id.in_(self.research_point_ids)
                ).all()
            ],
            "cta_id": self.cta_id,
            "prospect": prospect.to_dict() if prospect else None,
            "meta_data": {
                "research_points": [rp.to_dict() for rp in research_points],
                "cta": cta.to_dict() if cta else None,
            },
        }
