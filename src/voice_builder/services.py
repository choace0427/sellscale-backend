import json
from typing import Optional
import queue
import concurrent.futures

from sqlalchemy import func
from src.message_generation.services_stack_ranked_configurations import (
    get_sample_prompt_from_config_details,
)
from src.ml.fine_tuned_models import get_computed_prompt_completion
from model_import import (
    GeneratedMessageType,
    VoiceBuilderOnboarding,
    VoiceBuilderSamples,
    StackRankedMessageGenerationConfiguration,
    Client,
    ClientArchetype,
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
        Prospect.query.filter_by(client_id=client_id)
        .order_by(func.random())
        .limit(n)
        .all()
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


def get_voice_builder_samples(voice_builder_onboarding_id: int):
    voice_builder_samples: list[
        VoiceBuilderSamples
    ] = VoiceBuilderSamples.query.filter_by(
        voice_builder_onboarding_id=voice_builder_onboarding_id
    ).all()
    return [x.to_dict() for x in voice_builder_samples]


def create_voice_builder_samples(
    voice_builder_onboarding_id: int,
    n: int,
):
    # Using existing samples to reinforce the new sample generation
    computed_prompt = generate_computed_prompt(
        voice_builder_onboarding_id=voice_builder_onboarding_id
    )

    results_queue = queue.Queue()
    max_threads = 3

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [
            executor.submit(
                create_voice_builder_sample,
                voice_builder_onboarding_id=voice_builder_onboarding_id,
                computed_prompt=computed_prompt,
            )
        ]
        concurrent.futures.wait(futures)

    samples = []
    while not results_queue.empty():
        result = results_queue.get()
        samples.append(result)

    # samples = []
    # for _ in range(n):
    #     success, sample = create_voice_builder_sample(
    #         voice_builder_onboarding_id=voice_builder_onboarding_id,
    #         computed_prompt=computed_prompt,
    #     )
    #     if success: samples.append(sample)
    return samples


def create_voice_builder_sample(voice_builder_onboarding_id: int, computed_prompt: str, queue: queue.Queue):
    voice_builder_onboarding: VoiceBuilderOnboarding = VoiceBuilderOnboarding.query.get(
        voice_builder_onboarding_id
    )
    archetype_id = voice_builder_onboarding.client_archetype_id
    (
        prompt,
        _,
        research_point_ids,
        cta_id,
        bio_data,
        prospect_id,
    ) = get_sample_prompt_from_config_details(
        generated_message_type=voice_builder_onboarding.generated_message_type.value,
        research_point_types=[x.value for x in ResearchPointType],
        configuration_type="DEFAULT",
        client_id=voice_builder_onboarding.client_id,
        archetype_id=archetype_id,
    )

    completion, final_prompt = get_computed_prompt_completion(
        computed_prompt=computed_prompt,
        prompt=prompt,
    )

    voice_builder_sample: VoiceBuilderSamples = VoiceBuilderSamples(
        voice_builder_onboarding_id=voice_builder_onboarding_id,
        sample_readable_data=json.dumps(bio_data),
        sample_prompt=prompt,
        sample_final_prompt=final_prompt,
        sample_completion=completion,
        research_point_ids=research_point_ids,
        cta_id=cta_id,
        prospect_id=prospect_id,
    )
    db.session.add(voice_builder_sample)
    db.session.commit()

    queue.put(voice_builder_sample.to_dict())

    return True, voice_builder_sample.to_dict()


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
    if voice_builder_sample:
        db.session.delete(voice_builder_sample)
        db.session.commit()
    return True


def generate_computed_prompt(voice_builder_onboarding_id: int):
    voice_builder_onboarding: VoiceBuilderOnboarding = VoiceBuilderOnboarding.query.get(
        voice_builder_onboarding_id
    )
    samples: list[VoiceBuilderSamples] = VoiceBuilderSamples.query.filter_by(
        voice_builder_onboarding_id=voice_builder_onboarding_id
    ).all()

    if len(samples) == 0:
        # Use default example, if no samples exist
        sample_str = "--\n\nprompt: {prompt}\ncompletion: {completion}\n\n".format(
            prompt="name: Kumar Dharajan<>industry: Hospital & Health Care<>company: Clover Health<>title: Chief Clinician, Clover Health Partners Direct Contracting Entity (DCE)<>notes: -They are an experienced healthcare executive and health services researcher with regulatory experience and passion for creating technology-forward models of care to improve health outcomes for the Medicare population.\n-6-year anniversary at Clover Health is coming up.\n-Would love to talk about what issues you're seeing in executive staffing in New England.<>response:",
            completion="Hi Kumar! First off, happy almost 6-year anniversary at Clover Health! I admire your passion for creating technology-forward models of care to improve health outcomes for the Medicare population. I'd love to talk about any issues you're seeing in executive staffing in New England. Open to connect?",
        )
    else:
        sample_str = "".join(
            [
                "--\n\nprompt: {prompt}\ncompletion: {completion}\n\n".format(
                    prompt=sample.sample_prompt,
                    completion=sample.sample_completion,
                )
                for sample in samples
            ]
        )


    suffix = "\nprompt: {prompt}\ncompletion:"

    computed_prompt = """
{instruction}

## Here are a couple examples
{sample_str}
--
{suffix}
    """.format(
        instruction=voice_builder_onboarding.instruction,
        sample_str=sample_str,
        suffix=suffix,
    )

    return computed_prompt


def convert_voice_builder_onboarding_to_stack_ranked_message_config(
    voice_builder_onboarding_id: int,
):
    """
    Converts a voice builder onboarding to a stack ranked message config.
    """
    voice_builder_onboarding: VoiceBuilderOnboarding = VoiceBuilderOnboarding.query.get(
        voice_builder_onboarding_id
    )
    computed_prompt = generate_computed_prompt(voice_builder_onboarding_id)

    client: Client = Client.query.get(voice_builder_onboarding.client_id)
    company_name = client.company

    sub_title = "Default"
    archetype: ClientArchetype = ClientArchetype.query.get(
        voice_builder_onboarding.client_archetype_id
    )
    if archetype:
        sub_title = archetype.archetype
    srmc_name = "{company_name} - {sub_title} ({generated_message_type})".format(
        company_name=company_name,
        sub_title=sub_title,
        generated_message_type=voice_builder_onboarding.generated_message_type.value,
    )

    priority = 4
    if archetype:
        priority = 5

    srmc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration(
            configuration_type="DEFAULT",
            generated_message_type=voice_builder_onboarding.generated_message_type,
            research_point_types=[x.value for x in ResearchPointType],
            instruction=voice_builder_onboarding.instruction,
            computed_prompt=computed_prompt,
            active=True,
            always_enable=False,
            name=srmc_name,
            client_id=voice_builder_onboarding.client_id,
            archetype_id=voice_builder_onboarding.client_archetype_id,
            priority=priority,
        )
    )
    db.session.add(srmc)
    db.session.commit()

    voice_builder_onboarding.stack_ranked_message_generation_configuration_id = srmc.id
    db.session.add(voice_builder_onboarding)
    db.session.commit()

    return srmc
