import json
from typing import Optional
from src.message_generation.services_stack_ranked_configurations import (
    get_sample_prompt_from_config_details,
)
from src.ml.fine_tuned_models import get_computed_prompt_completion
from model_import import (
    GeneratedMessageType,
    VoiceBuilderOnboarding,
    VoiceBuilderSamples,
    StackRankedMessageGenerationConfiguration,
)
from model_import import Prospect, ResearchPointType
from src.research.linkedin.services import get_research_and_bullet_points_new
from app import db, celery


@celery.task
def generate_prospect_research(prospect_id: int):
    get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)


def conduct_research_for_n_prospects(
    client_id: int,
    n: int = 10,
) -> bool:
    """Triggers research for n prospects for a given client."""
    prospects: list[Prospect] = (
        Prospect.query.filter_by(client_id=client_id).limit(n).all()
    )
    for prospect in prospects:
        prospect_id = prospect.id
        generate_prospect_research.delay(prospect_id)
    return True


def create_voice_builder_onboarding(
    client_id: int,
    generated_message_type: GeneratedMessageType,
    instruction: str,
    client_archetype_id: Optional[int] = None,
) -> VoiceBuilderOnboarding:
    """Creates a voice builder onboarding for a given client."""
    voice_builder_onboarding: VoiceBuilderOnboarding = VoiceBuilderOnboarding(
        client_id=client_id,
        generated_message_type=generated_message_type,
        instruction=instruction,
        client_archetype_id=client_archetype_id,
    )
    db.session.add(voice_builder_onboarding)
    db.session.commit()
    return voice_builder_onboarding


def update_voice_builder_onboarding_instruction(
    voice_builder_onboarding_id: int,
    updated_instruction: str,
):
    """
    Updates the instruction for a given voice builder onboarding.
    """
    voice_builder_onboarding: VoiceBuilderOnboarding = VoiceBuilderOnboarding.query.get(
        voice_builder_onboarding_id
    )
    voice_builder_onboarding.instruction = updated_instruction
    db.session.add(voice_builder_onboarding)
    db.session.commit()
    return voice_builder_onboarding


def create_voice_builder_samples(
    voice_builder_onboarding_id: int,
    n: int,
):
    for _ in range(n):
        create_voice_builder_sample(
            voice_builder_onboarding_id=voice_builder_onboarding_id
        )


def create_voice_builder_sample(voice_builder_onboarding_id: int):
    voice_builder_onboarding: VoiceBuilderOnboarding = VoiceBuilderOnboarding.query.get(
        voice_builder_onboarding_id
    )
    (
        prompt,
        _,
        research_point_ids,
        cta_id,
        bio_data,
    ) = get_sample_prompt_from_config_details(
        generated_message_type=voice_builder_onboarding.generated_message_type.value,
        research_point_types=[x.value for x in ResearchPointType],
        configuration_type="DEFAULT",
        client_id=voice_builder_onboarding.client_id,
    )
    computed_prompt = """
{instruction}

data: {prompt}
completion:""".format(
        instruction=voice_builder_onboarding.instruction, prompt=prompt
    )

    completion, _ = get_computed_prompt_completion(
        computed_prompt=computed_prompt,
        prompt=prompt,
    )

    voice_builder_sample: VoiceBuilderSamples = VoiceBuilderSamples(
        voice_builder_onboarding_id=voice_builder_onboarding_id,
        sample_readable_data=json.dumps(bio_data),
        sample_prompt=prompt,
        sample_completion=completion,
        research_point_ids=research_point_ids,
        cta_id=cta_id,
    )
    db.session.add(voice_builder_sample)
    db.session.commit()

    return prompt, computed_prompt, completion


def edit_voice_builder_sample(
    voice_builder_sample_id: int,
    updated_completion: str,
):
    voice_builder_sample = VoiceBuilderSamples.query.get(voice_builder_sample_id)
    voice_builder_sample.sample_completion = updated_completion
    db.session.add(voice_builder_sample)
    db.session.commit()
    return voice_builder_sample


def delete_voice_builder_sample(
    voice_builder_sample_id: int,
):
    voice_builder_sample = VoiceBuilderSamples.query.get(voice_builder_sample_id)
    db.session.delete(voice_builder_sample)
    db.session.commit()
    return True


def convert_voice_builder_onboarding_to_stack_ranked_message_config(
    voice_builder_onboarding_id: int,
):
    # convert voice builder onboarding to stack ranked message config
    raise NotImplementedError
