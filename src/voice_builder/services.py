from message_generation.services_stack_ranked_configurations import (
    get_sample_prompt_from_config_details,
)
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
) -> VoiceBuilderOnboarding:
    """Creates a voice builder onboarding for a given client."""
    voice_builder_onboarding: VoiceBuilderOnboarding = VoiceBuilderOnboarding(
        client_id=client_id,
        generated_message_type=generated_message_type,
        instruction=instruction,
    )
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
    # get_sample_prompt_from_config_details(
    #     generated_message_type=voice_builder_onboarding.generated_message_type.value,
    #     research_point_types=[
    #         research_point_type.value
    #         for research_point_type in ResearchPointType._value2member_map_.keys()
    #     ],
    # )


def edit_voice_builder_sample(
    voice_builder_sample_id: int,
    updated_completion: str,
):
    # edit voice builder sample
    raise NotImplementedError


def delete_voice_builder_sample(
    voice_builder_sample_id: int,
):
    # delete voice builder sample
    raise NotImplementedError


def convert_voice_builder_onboarding_to_stack_ranked_message_config(
    voice_builder_onboarding_id: int,
):
    # convert voice builder onboarding to stack ranked message config
    raise NotImplementedError
