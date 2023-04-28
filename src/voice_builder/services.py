from model_import import (
    GeneratedMessageType,
    VoiceBuilderOnboarding,
    VoiceBuilderSamples,
    StackRankedMessageGenerationConfiguration,
)


def conduct_research_for_n_prospects(
    client_id: int,
    n: int,
):
    # conduct research for n prospects in client id
    raise NotImplementedError


def create_voice_builder_onboarding(
    client_id: int,
    generated_message_type: GeneratedMessageType,
    instruction: str,
):
    # create vbo object
    raise NotImplementedError


def create_voice_builder_samples(
    voice_builder_onboarding_id: int,
    n: int,
):
    # create voice builder samples
    raise NotImplementedError


def create_voice_builder_sample(
    sample_readable_data: str,
    sample_prompt: str,
    sample_completion: str,
):
    # create voice builder sample
    raise NotImplementedError


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
