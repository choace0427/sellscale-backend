import json
from typing import Optional
from app import app
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
from model_import import Prospect
from src.ml.rule_engine import run_message_rule_engine_on_linkedin_completion
from src.research.linkedin.services import get_research_and_bullet_points_new
from app import db, celery
from src.research.services import get_all_research_point_types


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
    voice_builder_samples: list[VoiceBuilderSamples] = (
        VoiceBuilderSamples.query.filter_by(
            voice_builder_onboarding_id=voice_builder_onboarding_id
        )
        .order_by(VoiceBuilderSamples.id.desc())
        .all()
    )
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
    max_threads = 5

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [
            executor.submit(
                create_voice_builder_sample,
                voice_builder_onboarding_id=voice_builder_onboarding_id,
                computed_prompt=computed_prompt,
                queue=results_queue,
            )
            for _ in range(n)
        ]

    # Wait for all tasks to complete
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
    #         queue=None,
    #     )
    #     if success:
    #         samples.append(sample)

    return samples


def create_voice_builder_sample(
    voice_builder_onboarding_id: int,
    computed_prompt: str,
    queue: Optional[queue.Queue] = None,
):
    with app.app_context():
        voice_builder_onboarding: VoiceBuilderOnboarding = (
            VoiceBuilderOnboarding.query.get(voice_builder_onboarding_id)
        )
        archetype_id = voice_builder_onboarding.client_archetype_id
        archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)

        research_point_types = get_all_research_point_types(
            archetype.client_sdr_id, names_only=True, archetype_id=archetype_id
        )
        transformer_blocklist = archetype.transformer_blocklist_initial
        filtered_research_point_types: any = [
            x for x in research_point_types if x not in transformer_blocklist
        ]

        (
            prompt,
            _,
            research_point_ids,
            cta_id,
            bio_data,
            prospect_id,
        ) = get_sample_prompt_from_config_details(
            generated_message_type=voice_builder_onboarding.generated_message_type.value,
            research_point_types=filtered_research_point_types,
            configuration_type="DEFAULT",
            client_id=voice_builder_onboarding.client_id,
            archetype_id=archetype_id,
        )

        attempts = 0
        while attempts < 2:
            completion, final_prompt = get_computed_prompt_completion(
                computed_prompt=computed_prompt,
                prompt=prompt,
            )

            # Run rule engine. For now, we don't need to use the problems or highlighted words
            (
                completion,
                problems,
                blocking_problems,
                highlighted_words,
            ) = run_message_rule_engine_on_linkedin_completion(
                completion=completion,
                prompt=prompt,
                run_arree=True,
            )

            if completion:
                break

            attempts += 1

        voice_builder_sample: VoiceBuilderSamples = VoiceBuilderSamples(
            voice_builder_onboarding_id=voice_builder_onboarding_id,
            sample_readable_data=json.dumps(bio_data),
            sample_prompt=prompt,
            sample_final_prompt=final_prompt,
            sample_completion=completion,
            sample_problems=None,
            sample_highlighted_words=None,
            research_point_ids=research_point_ids,
            cta_id=cta_id,
            prospect_id=prospect_id,
        )
        db.session.add(voice_builder_sample)
        db.session.commit()

        if queue:
            queue.put(voice_builder_sample.to_dict())

        return True, voice_builder_sample.to_dict()


def edit_voice_builder_sample(
    voice_builder_sample_id: int,
    updated_completion: str,
):
    voice_builder_sample: VoiceBuilderSamples = VoiceBuilderSamples.query.get(
        voice_builder_sample_id
    )

    (
        _,
        problems,
        blocking_problems,
        highlighted_words,
    ) = run_message_rule_engine_on_linkedin_completion(
        completion=updated_completion,
        prompt=voice_builder_sample.sample_prompt,
        run_arree=False,
    )

    voice_builder_sample.sample_completion = updated_completion
    voice_builder_sample.sample_problems = problems
    voice_builder_sample.sample_highlighted_words = highlighted_words
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

The message should be no longer than 300 characters.

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
    voice_builder_samples = VoiceBuilderSamples.query.filter_by(
        voice_builder_onboarding_id=voice_builder_onboarding_id
    ).all()
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

    prompt_1, prompt_2, prompt_3, prompt_4, prompt_5, prompt_6, prompt_7 = (
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    (
        completion_1,
        completion_2,
        completion_3,
        completion_4,
        completion_5,
        completion_6,
        completion_7,
    ) = (None, None, None, None, None, None, None)

    if len(voice_builder_samples) > 0:
        prompt_1 = voice_builder_samples[0].sample_prompt
        completion_1 = voice_builder_samples[0].sample_completion
    if len(voice_builder_samples) > 1:
        prompt_2 = voice_builder_samples[1].sample_prompt
        completion_2 = voice_builder_samples[1].sample_completion
    if len(voice_builder_samples) > 2:
        prompt_3 = voice_builder_samples[2].sample_prompt
        completion_3 = voice_builder_samples[2].sample_completion
    if len(voice_builder_samples) > 3:
        prompt_4 = voice_builder_samples[3].sample_prompt
        completion_4 = voice_builder_samples[3].sample_completion
    if len(voice_builder_samples) > 4:
        prompt_5 = voice_builder_samples[4].sample_prompt
        completion_5 = voice_builder_samples[4].sample_completion
    if len(voice_builder_samples) > 5:
        prompt_6 = voice_builder_samples[5].sample_prompt
        completion_6 = voice_builder_samples[5].sample_completion
    if len(voice_builder_samples) > 6:
        prompt_7 = voice_builder_samples[6].sample_prompt
        completion_7 = voice_builder_samples[6].sample_completion

    priority = 4
    if archetype:
        priority = 5

    baseline_srmc: Optional[
        StackRankedMessageGenerationConfiguration
    ] = StackRankedMessageGenerationConfiguration.query.filter_by(
        client_id=voice_builder_onboarding.client_id, archetype_id=None
    ).first()

    srmc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration(
            configuration_type="DEFAULT",
            generated_message_type=voice_builder_onboarding.generated_message_type,
            research_point_types=get_all_research_point_types(
                archetype.client_sdr_id, names_only=True, archetype_id=archetype.id
            ),
            instruction=voice_builder_onboarding.instruction,
            computed_prompt=computed_prompt,
            active=True,
            always_enable=False,
            name=srmc_name,
            client_id=voice_builder_onboarding.client_id,
            archetype_id=voice_builder_onboarding.client_archetype_id,
            priority=priority,
            prompt_1=prompt_1,
            completion_1=completion_1,
            prompt_2=prompt_2,
            completion_2=completion_2,
            prompt_3=prompt_3,
            completion_3=completion_3,
            prompt_4=prompt_4,
            completion_4=completion_4,
            prompt_5=prompt_5,
            completion_5=completion_5,
            prompt_6=prompt_6,
            completion_6=completion_6,
            prompt_7=prompt_7,
            completion_7=completion_7,
        )
    )
    db.session.add(srmc)

    if not baseline_srmc:
        new_baseline_srmc: StackRankedMessageGenerationConfiguration = (
            StackRankedMessageGenerationConfiguration(
                configuration_type="DEFAULT",
                generated_message_type=voice_builder_onboarding.generated_message_type,
                research_point_types=get_all_research_point_types(
                    archetype.client_sdr_id, names_only=True, archetype_id=archetype.id
                ),
                instruction=voice_builder_onboarding.instruction,
                computed_prompt=computed_prompt,
                active=True,
                always_enable=True,
                name="Baseline - {company_name}".format(
                    company_name=company_name,
                ),
                client_id=voice_builder_onboarding.client_id,
                archetype_id=None,
                priority=1,
                prompt_1=prompt_1,
                completion_1=completion_1,
                prompt_2=prompt_2,
                completion_2=completion_2,
                prompt_3=prompt_3,
                completion_3=completion_3,
                prompt_4=prompt_4,
                completion_4=completion_4,
                prompt_5=prompt_5,
                completion_5=completion_5,
                prompt_6=prompt_6,
                completion_6=completion_6,
                prompt_7=prompt_7,
                completion_7=completion_7,
            )
        )
        db.session.add(new_baseline_srmc)

    db.session.commit()

    srmc_dict = srmc.to_dict()

    voice_builder_onboarding.stack_ranked_message_generation_configuration_id = srmc.id
    db.session.add(voice_builder_onboarding)
    db.session.commit()

    # Make this the only active voice
    other_srmcs: list[StackRankedMessageGenerationConfiguration] = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            archetype_id=voice_builder_onboarding.client_archetype_id
        )
        .filter(StackRankedMessageGenerationConfiguration.id != srmc.id)
        .all()
    )
    for o_srmc in other_srmcs:
        o_srmc.active = False
        db.session.add(o_srmc)
    db.session.commit()

    return srmc_dict
