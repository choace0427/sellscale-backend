from sqlalchemy import or_
from src.ml.rule_engine import get_adversarial_ai_approval
from src.ml.models import GNLPModelType
from model_import import (
    ClientArchetype,
    GeneratedMessageType,
    GeneratedMessage,
    EmailSchema,
    GeneratedMessageStatus,
    ProspectEmail,
    ProspectStatus,
    OutboundCampaign,
    GeneratedMessageFeedback,
    GeneratedMessageJob,
    GeneratedMessageJobQueue,
    GeneratedMessageJobStatus,
    GeneratedMessageCTA,
    GeneratedMessageEditRecord,
    StackRankedMessageGenerationConfiguration,
    ConfigurationType,
    GeneratedMessageEditRecord,
)
from typing import Optional
from src.ml.rule_engine import run_message_rule_engine
from src.ml.services import ai_email_prompt, generate_email
from src.ml_adversary.services import run_adversary
from src.email_outbound.models import ProspectEmailStatus
from src.research.models import ResearchPayload, ResearchPoints
from src.utils.random_string import generate_random_alphanumeric
from src.research.linkedin.services import get_research_and_bullet_points_new
from model_import import Prospect
from ..ml.fine_tuned_models import (
    get_custom_completion_for_client,
    get_personalized_first_line_for_client,
    get_config_completion,
    get_few_shot_baseline_prompt,
)
from src.email_outbound.services import create_prospect_email
from src.message_generation.ner_exceptions import ner_exceptions, title_abbreviations
from ..utils.abstract.attr_utils import deep_get
import random
from app import db, celery
from tqdm import tqdm
import openai
import re
import os
import datetime
from src.research.linkedin.services import (
    delete_research_points_and_payload_by_prospect_id,
)
from src.message_generation.services_stack_ranked_configurations import (
    get_top_stack_ranked_config_ordering,
)


HUGGING_FACE_KEY = os.environ.get("HUGGING_FACE_KEY")


def get_messages_queued_for_outreach(
    client_sdr_id: int, limit: Optional[int] = 5, offset: Optional[int] = 0
) -> tuple[list[dict], int]:
    """Gets the messages queued for outreach for a client SDR

    Args:
        client_sdr_id (int): ID of the client SDR
        limit (Optional[int], optional): Number of messages to grab. Defaults to 5.
        offset (Optional[int], optional): Offset to start grabbing messages from. Defaults to 0.

    Returns:
        list[dict]: List of messages queued for outreach
    """
    joined_prospect_message = (
        db.session.query(
            Prospect.id.label("prospect_id"),
            Prospect.full_name.label("full_name"),
            Prospect.title.label("title"),
            Prospect.company.label("company"),
            Prospect.img_url.label("img_url"),
            GeneratedMessage.id.label("message_id"),
            GeneratedMessage.completion.label("completion"),
        )
        .join(
            GeneratedMessage,
            Prospect.approved_outreach_message_id == GeneratedMessage.id,
        )
        .filter(
            Prospect.client_sdr_id == client_sdr_id,
            GeneratedMessage.message_status
            == GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
            or_(
                GeneratedMessage.pb_csv_count <= 2,
                GeneratedMessage.pb_csv_count == None,
            ),  # Only grab messages that have not been sent twice
        )
    )

    total_count = joined_prospect_message.count()

    joined_prospect_message = (
        joined_prospect_message.order_by(GeneratedMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    message_list = []
    for row in joined_prospect_message:
        message_list.append(
            {
                "prospect_id": row.prospect_id,
                "full_name": row.full_name,
                "title": row.title,
                "company": row.company,
                "img_url": row.img_url,
                "message_id": row.message_id,
                "completion": row.completion,
            }
        )

    return message_list, total_count


@celery.task(bind=True, max_retries=3)
def generate_outreaches_for_prospect_list_from_multiple_ctas(
    self, prospect_ids: list, cta_ids: list, outbound_campaign_id: int
):
    try:
        for i, prospect_id in enumerate(prospect_ids):
            cta_id = cta_ids[i % len(cta_ids)]

            # Check if there is already a job for this Prospect under this Campaign
            job_exists = GeneratedMessageJobQueue.query.filter(
                GeneratedMessageJobQueue.prospect_id == prospect_id,
                GeneratedMessageJobQueue.outbound_campaign_id == outbound_campaign_id,
            ).first()
            if job_exists:
                continue

            # Create a generate message job for the prospect
            gm_job: GeneratedMessageJobQueue = GeneratedMessageJobQueue(
                prospect_id=prospect_id,
                outbound_campaign_id=outbound_campaign_id,
                status=GeneratedMessageJobStatus.PENDING,
                attempts=0,
            )
            db.session.add(gm_job)
            db.session.commit()

            # Research and generate outreaches for the prospect
            research_and_generate_outreaches_for_prospect.apply_async(
                [
                    prospect_id,
                    outbound_campaign_id,
                    cta_id,
                    gm_job.id,
                ],
                countdown=i * 10,
            )
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def update_generated_message_job_queue_status(
    gm_job_id: int,
    status: GeneratedMessageJobStatus,
    error_message: Optional[str] = None,
) -> bool:
    """Updates the status of a GeneratedMessageJobQueue job

    Args:
        gm_job_id (int): ID of the GeneratedMessageJobQueue job
        status (GeneratedMessageJobStatus): The new status of the job
        error_message (Optional[str], optional): The error message to attach in case there is an error. Defaults to None.

    Returns:
        bool: True if the job was updated, False otherwise
    """
    if not gm_job_id:
        return True
    gm_job: GeneratedMessageJobQueue = GeneratedMessageJobQueue.query.get(gm_job_id)
    if gm_job:
        gm_job.status = status.value
        gm_job.error_message = error_message
        db.session.add(gm_job)
        db.session.commit()

    return True


def increment_generated_message_job_queue_attempts(gm_job_id: int) -> bool:
    """Increments the number of attempts for a GeneratedMessageJobQueue job

    Args:
        gm_job_id (int): ID of the GeneratedMessageJobQueue job

    Returns:
        bool: True if the job was updated, False otherwise
    """
    gm_job: GeneratedMessageJobQueue = GeneratedMessageJobQueue.query.get(gm_job_id)
    if gm_job:
        if gm_job.attempts:
            gm_job.attempts += 1
        else:
            gm_job.attempts = 1
        db.session.add(gm_job)
        db.session.commit()

    return True


@celery.task(bind=True, max_retries=3)
def research_and_generate_outreaches_for_prospect(
    self,
    prospect_id: int,
    outbound_campaign_id: int,
    cta_id: str = None,
    gm_job_id: int = None,
) -> tuple[bool, str]:
    try:
        from src.research.linkedin.services import get_research_and_bullet_points_new

        # Mark the job as in progress
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.IN_PROGRESS
        )

        # Increment the number of attempts
        increment_generated_message_job_queue_attempts(gm_job_id)

        # Check if the prospect exists
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            update_generated_message_job_queue_status(
                gm_job_id,
                GeneratedMessageJobStatus.FAILED,
                error_message="Prospect does not exist",
            )
            return (False, "Prospect does not exist")

        # Create research payload and bullet points for the Prospect
        get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

        # Generate outreaches for the Prospect
        generate_linkedin_outreaches_with_configurations(
            prospect_id=prospect_id,
            cta_id=cta_id,
            outbound_campaign_id=outbound_campaign_id,
        )

        # Run auto approval
        batch_approve_message_generations_by_heuristic(prospect_ids=[prospect_id])

        # Mark the job as completed
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.COMPLETED
        )
    except Exception as e:
        db.session.rollback()
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.FAILED, error_message=str(e)
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)


def generate_prompt(prospect_id: int, notes: str = ""):
    from model_import import Prospect
    from src.utils.converters.string_converters import clean_company_name

    p: Prospect = Prospect.query.get(prospect_id)
    bio_data = {
        "full_name": p.full_name,
        "industry": p.industry,
        "company": clean_company_name(p.company),
        "title": p.title,
        "notes": notes,
        "cleaned_bio": p.linkedin_bio,
    }
    prompt = "name: {full_name}<>industry: {industry}<>company: {company}<>title: {title}<>notes: {notes}<>response:".format(
        **bio_data
    )
    prompt = (
        prompt.replace('"', "").replace("\\", "").replace("\n", "\\n").replace("\r", "")
    )

    return prompt, bio_data


def generate_batches_of_research_points(
    points: list, n: int = 1, num_per_perm: int = 2
):
    perms = []
    for i in range(n):
        sample = [x for x in random.sample(points, min(len(points), num_per_perm))]
        perms.append(sample)
    return perms


def generate_batch_of_research_points_from_config(
    prospect_id: int,
    config: Optional[StackRankedMessageGenerationConfiguration],
    n: int = 1,
):
    all_research_points: list = ResearchPoints.get_research_points_by_prospect_id(
        prospect_id=prospect_id
    )

    # If there are no research points, return an empty list
    if not all_research_points or len(all_research_points) == 0:
        return []

    if not config:
        return generate_batches_of_research_points(
            points=all_research_points, n=n, num_per_perm=2
        )
    allowed_research_point_types_in_config = [x for x in config.research_point_types]

    research_points = [
        x
        for x in all_research_points
        if x.research_point_type.value in allowed_research_point_types_in_config
    ]

    num_per_perm = (
        len(config.research_point_types)
        if config.configuration_type == ConfigurationType.STRICT
        else 2
    )

    return generate_batches_of_research_points(
        points=research_points, n=n, num_per_perm=num_per_perm
    )


def get_notes_and_points_from_perm(perm, cta_id: int = None):
    from model_import import (
        GeneratedMessageCTA,
    )

    d = ["-" + x.value for x in perm]
    cta = None
    if cta_id:
        cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)

    if cta:
        d.append("-" + cta.text_value)
    notes = "\n".join(d)

    research_points = [x.id for x in perm]

    return notes, research_points, cta


def has_any_linkedin_messages(prospect_id: int):
    from model_import import GeneratedMessage

    messages: list = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_type == GeneratedMessageType.LINKEDIN,
    ).all()
    return len(messages) > 0


def generate_linkedin_outreaches_with_configurations(
    prospect_id: int, outbound_campaign_id: int, cta_id: str = None
):
    if has_any_linkedin_messages(prospect_id=prospect_id):
        return None
    NUM_GENERATIONS = 3
    for i in range(NUM_GENERATIONS):
        TOP_CONFIGURATION: Optional[
            StackRankedMessageGenerationConfiguration
        ] = get_top_stack_ranked_config_ordering(
            generated_message_type=GeneratedMessageType.LINKEDIN.value,
            prospect_id=prospect_id,
        )
        perms = generate_batch_of_research_points_from_config(
            prospect_id=prospect_id, config=TOP_CONFIGURATION, n=1
        )

        if not perms or len(perms) == 0:
            raise ValueError("No research point permutations")

        outreaches = []

        for perm in perms:
            notes, research_points, _ = get_notes_and_points_from_perm(
                perm, cta_id=cta_id
            )
            prompt, _ = generate_prompt(prospect_id=prospect_id, notes=notes)

            if len(research_points) == 0:
                continue
            completion, few_shot_prompt = get_config_completion(
                TOP_CONFIGURATION, prompt
            )

            outreaches.append(completion)

            message: GeneratedMessage = GeneratedMessage(
                prospect_id=prospect_id,
                research_points=research_points,
                prompt=prompt,
                completion=completion,
                message_status=GeneratedMessageStatus.DRAFT,
                outbound_campaign_id=outbound_campaign_id,
                adversarial_ai_prediction=False,
                message_cta=cta_id,
                message_type=GeneratedMessageType.LINKEDIN,
                few_shot_prompt=few_shot_prompt,
                stack_ranked_message_generation_configuration_id=TOP_CONFIGURATION.id
                if TOP_CONFIGURATION
                else None,
            )
            db.session.add(message)
            db.session.commit()

    return outreaches


def generate_linkedin_outreaches(
    prospect_id: int, outbound_campaign_id: int, cta_id: str = None
):
    from model_import import (
        GeneratedMessage,
        GeneratedMessageStatus,
    )
    from src.message_generation.services_few_shot_generations import (
        generate_few_shot_generation_completion,
        can_generate_with_few_shot,
    )

    if has_any_linkedin_messages(prospect_id=prospect_id):
        return None

    research_points_list: list[
        ResearchPoints
    ] = ResearchPoints.get_research_points_by_prospect_id(prospect_id)

    perms = generate_batches_of_research_points(points=research_points_list, n=4)

    if not perms or len(perms) == 0:
        raise ValueError("No research point permutations")

    outreaches = []
    for perm in perms:
        notes, research_points, cta = get_notes_and_points_from_perm(perm, cta_id)

        able_to_generate_with_few_shot = can_generate_with_few_shot(
            prospect_id=prospect_id
        )
        # If you are able to generate with few shot, generate with few shot. Else
        #       default to the normal generation using baseline / fine tuned model for
        #       the archetype
        if not able_to_generate_with_few_shot:
            prompt, _ = generate_prompt(prospect_id=prospect_id, notes=notes)
            model_id = 5
            completions = get_few_shot_baseline_prompt(prompt=prompt)
            instruction_id = None
            few_shot_prompt = None
        else:
            (
                completions,
                model_id,
                prompt,
                instruction_id,
                few_shot_prompt,
            ) = generate_few_shot_generation_completion(
                prospect_id=prospect_id, notes=notes
            )

        for completion in completions:
            outreaches.append(completion)

            message: GeneratedMessage = GeneratedMessage(
                prospect_id=prospect_id,
                gnlp_model_id=model_id,
                research_points=research_points,
                prompt=prompt,
                completion=completion,
                message_status=GeneratedMessageStatus.DRAFT,
                outbound_campaign_id=outbound_campaign_id,
                adversarial_ai_prediction=False,
                message_cta=cta.id if cta else None,
                message_type=GeneratedMessageType.LINKEDIN,
                generated_message_instruction_id=instruction_id,
                few_shot_prompt=few_shot_prompt,
            )
            db.session.add(message)
            db.session.commit()

    batch_approve_message_generations_by_heuristic(prospect_ids=[prospect_id])

    return outreaches


def create_new_edit_message_record(
    generated_message_id: int,
    original_text: str,
    edited_text: str,
    editor_id=None,
):
    edit: GeneratedMessageEditRecord = GeneratedMessageEditRecord(
        generated_message_id=generated_message_id,
        original_text=original_text,
        edited_text=edited_text,
        editor_id=editor_id,
    )
    db.session.add(edit)
    db.session.commit()

    return True


def update_linkedin_message_for_prospect_id(prospect_id: int, update: str):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return False
    message_id = prospect.approved_outreach_message_id
    update_message(
        message_id=message_id,
        update=update,
    )


def update_message(message_id: int, update: str, editor_id=None):
    from model_import import GeneratedMessage

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    if not message:
        return False

    original_text = message.completion
    edited_text = update

    create_new_edit_message_record(
        generated_message_id=message_id,
        original_text=original_text,
        edited_text=edited_text,
        editor_id=editor_id,
    )

    message.completion = update

    # Only mark the message as human_edited if the character difference is more than 2 characters.
    if abs(len(original_text) - len(edited_text)) >= 2:
        message.human_edited = True
    else:
        diff_count = abs(len(original_text) - len(edited_text))
        for i in range(min(len(original_text), len(edited_text))):
            if original_text[i] != edited_text[i]:
                diff_count += 1
                if diff_count >= 2:
                    message.human_edited = True
                    break

    db.session.add(message)
    db.session.commit()

    run_message_rule_engine(message_id=message.id)

    return True


def approve_message(message_id: int):
    from model_import import GeneratedMessage, GeneratedMessageStatus, Prospect

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message_type = message.message_type
    prospect_id = message.prospect_id
    other_approved_messages = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_status == GeneratedMessageStatus.APPROVED,
        GeneratedMessage.message_type == message_type,
        GeneratedMessage.id != message_id,
    ).all()
    for message in other_approved_messages:
        message.message_status = GeneratedMessageStatus.DRAFT
        db.session.add(message)
        db.session.commit()

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.message_status = GeneratedMessageStatus.APPROVED

    # try:
    #     mistake, fix, _ = run_adversary(message.prompt, message.completion)
    #     message.adversary_identified_mistake = mistake
    #     message.adversary_identified_fix = fix
    # except:
    #     # TODO: Include logging here in future
    #     pass

    db.session.add(message)

    message_id = message.id

    prospect_id = message.prospect_id
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = message.id
    db.session.add(prospect)

    db.session.commit()
    run_message_rule_engine(message_id=message_id)

    return True


def disapprove_message(message_id: int):
    from model_import import GeneratedMessage, GeneratedMessageStatus

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    prospect_id = message.prospect_id
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = None
    message.message_status = GeneratedMessageStatus.DRAFT
    db.session.add(message)
    db.session.add(prospect)
    db.session.commit()

    return True


def pick_new_approved_message_for_prospect(prospect_id: int, message_id: int):
    """Given a prospect, selects a new generated message that is not message_id."""
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message_type = message.message_type.value
    data = db.session.execute(
        """
            select length(completion), *
            from generated_message
            where prospect_id = {prospect_id}
                and message_type = '{message_type}'
            order by abs(270 - length(completion)) asc
        """.format(
            prospect_id=prospect_id,
            message_type=message_type,
        )
    ).fetchall()
    ids = [x["id"] for x in data]
    new_index = (ids.index(message_id) + 1) % len(ids)
    new_message_id = ids[new_index]
    approve_message(message_id=new_message_id)

    return True


def delete_message_generation_by_prospect_id(prospect_id: int):
    from model_import import GeneratedMessage

    messages: list = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_type == GeneratedMessageType.LINKEDIN,
    ).all()

    for message in messages:
        edits = GeneratedMessageEditRecord.query.filter(
            GeneratedMessageEditRecord.generated_message_id == message.id
        ).all()
        for edit in edits:
            db.session.delete(edit)
        db.session.commit()

    for message in messages:
        db.session.delete(message)
        db.session.commit()

    return True


def create_cta(archetype_id: int, text_value: str):
    duplicate_cta_exists = GeneratedMessageCTA.query.filter(
        GeneratedMessageCTA.archetype_id == archetype_id,
        GeneratedMessageCTA.text_value == text_value,
    ).first()
    if duplicate_cta_exists:
        return duplicate_cta_exists

    cta: GeneratedMessageCTA = GeneratedMessageCTA(
        archetype_id=archetype_id, text_value=text_value, active=True
    )
    db.session.add(cta)
    db.session.commit()

    return cta


def delete_cta(cta_id: int):
    from model_import import GeneratedMessageCTA

    generated_message_with_cta = GeneratedMessage.query.filter(
        GeneratedMessage.message_cta == cta_id
    ).first()
    if generated_message_with_cta:
        return False

    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)
    db.session.delete(cta)
    db.session.commit()

    return True


def toggle_cta_active(cta_id: int):
    from model_import import GeneratedMessageCTA

    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)
    cta.active = not cta.active
    db.session.add(cta)
    db.session.commit()

    return True


def get_personalized_first_line_from_prompt(
    archetype_id: int,
    model_type: GNLPModelType,
    prompt: str,
    research_points: list,
    prospect_id: int,
    outbound_campaign_id: int,
    config: Optional[StackRankedMessageGenerationConfiguration],
):
    if not config:
        completion, few_shot_prompt = get_personalized_first_line_for_client(
            archetype_id=archetype_id,
            model_type=model_type,
            prompt=prompt,
        )
    else:
        completion, few_shot_prompt = get_config_completion(config, prompt)

    personalized_first_line = GeneratedMessage(
        prospect_id=prospect_id,
        research_points=research_points,
        prompt=prompt,
        completion=completion,
        message_status=GeneratedMessageStatus.DRAFT,
        message_type=GeneratedMessageType.EMAIL,
        outbound_campaign_id=outbound_campaign_id,
        few_shot_prompt=few_shot_prompt,
        stack_ranked_message_generation_configuration_id=config.id if config else None,
    )
    db.session.add(personalized_first_line)
    db.session.commit()

    return personalized_first_line


@celery.task(bind=True, max_retries=3)
def create_and_start_email_generation_jobs(self, campaign_id: int):
    """Creates GeneratedMessageJobQueue objects for each prospect in the campaign and queues them.

    Args:
        campaign_id (int): The id of the campaign to generate emails for.

    Raises:
        self.retry: For any exception, retry the task a number of times.
    """
    try:
        campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
        prospect_ids = campaign.prospect_ids
        for i, prospect_id in enumerate(prospect_ids):
            # Check if a job already exists for this prospect
            job_exists = GeneratedMessageJobQueue.query.filter(
                GeneratedMessageJobQueue.prospect_id == prospect_id,
                GeneratedMessageJobQueue.outbound_campaign_id == campaign_id,
            ).first()
            if job_exists:
                continue

            # Create a generate message job for the prospect
            gm_job: GeneratedMessageJobQueue = GeneratedMessageJobQueue(
                prospect_id=prospect_id,
                outbound_campaign_id=campaign_id,
                status=GeneratedMessageJobStatus.PENDING,
                attempts=0,
            )
            db.session.add(gm_job)
            db.session.commit()

            # Generate the prospect email
            generate_prospect_email.apply_async(
                args=[prospect_id, campaign_id, gm_job.id], countdown=i * 10
            )
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3)
def generate_prospect_email(
    self, prospect_id: int, campaign_id: int, gm_job_id: int
) -> tuple[bool, str]:
    try:
        # Mark the job as in progress
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.IN_PROGRESS
        )

        # Increment the attempts
        increment_generated_message_job_queue_attempts(gm_job_id)

        # Check if the prospect exists
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_sdr_id = prospect.client_sdr_id
        if not prospect:
            update_generated_message_job_queue_status(
                gm_job_id,
                GeneratedMessageJobStatus.FAILED,
                error_message="Prospect does not exist",
            )
            return (False, "Prospect does not exist")

        # Check if the prospect already has a prospect_email
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect.approved_prospect_email_id
        )
        if prospect_email:
            update_generated_message_job_queue_status(
                gm_job_id,
                GeneratedMessageJobStatus.FAILED,
                error_message="Prospect already has a prospect_email entry",
            )
            return (False, "Prospect already has a prospect_email entry")

        # Create research points and payload for the prospect
        get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

        # Get the top configuration and research poitn permutations for the prospect
        NUM_GENERATIONS = 1  # number of ProspectEmail's to make
        TOP_CONFIGURATION = get_top_stack_ranked_config_ordering(
            generated_message_type=GeneratedMessageType.EMAIL.value,
            prospect_id=prospect_id,
        )
        perms = generate_batch_of_research_points_from_config(
            prospect_id=prospect_id, config=TOP_CONFIGURATION, n=NUM_GENERATIONS
        )

        # If there are no permutations, then fail the job
        if len(perms) == 0:
            update_generated_message_job_queue_status(
                gm_job_id,
                GeneratedMessageJobStatus.FAILED,
                "No research point permutations",
            )
            return (False, "No research point permutations")

        is_first_email = True
        for perm in perms:
            notes, research_points, _ = get_notes_and_points_from_perm(perm)
            prompt, _ = generate_prompt(prospect_id=prospect_id, notes=notes)

            if len(research_points) == 0:
                update_generated_message_job_queue_status(
                    gm_job_id, GeneratedMessageJobStatus.FAILED, "No research points"
                )
                return (False, "No research points")

            email_generation_prompt = ai_email_prompt(
                client_sdr_id=client_sdr_id,
                prospect_id=prospect_id,
            )
            email_data = generate_email(prompt=email_generation_prompt)
            subject = email_data["subject"]
            personalized_body = email_data["body"]

            personalized_subject_line = GeneratedMessage(
                prospect_id=prospect_id,
                outbound_campaign_id=campaign_id,
                research_points=research_points,
                prompt=prompt,
                completion=subject,
                message_status=GeneratedMessageStatus.DRAFT,
                message_type=GeneratedMessageType.EMAIL,
            )
            personalized_body = GeneratedMessage(
                prospect_id=prospect_id,
                outbound_campaign_id=campaign_id,
                research_points=research_points,
                prompt=prompt,
                completion=personalized_body,
                message_status=GeneratedMessageStatus.DRAFT,
                message_type=GeneratedMessageType.EMAIL,
            )
            db.session.add(personalized_subject_line)
            db.session.add(personalized_body)
            db.session.commit()

            # personalized_first_line = get_personalized_first_line_from_prompt(
            #     archetype_id=archetype_id,
            #     model_type=GNLPModelType.EMAIL_FIRST_LINE,
            #     prompt=prompt,
            #     research_points=research_points,
            #     prospect_id=prospect_id,
            #     outbound_campaign_id=campaign_id,
            #     config=TOP_CONFIGURATION,
            # )

            prospect_email: ProspectEmail = create_prospect_email(
                prospect_id=prospect_id,
                # personalized_first_line_id=personalized_first_line.id,
                personalized_subject_line_id=personalized_subject_line.id,
                personalized_body_id=personalized_body.id,
                outbound_campaign_id=campaign_id,
            )

            if is_first_email:
                mark_prospect_email_approved(
                    prospect_email_id=prospect_email.id,
                )
                is_first_email = False
    except Exception as e:
        db.session.rollback()
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.FAILED, str(e)
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)

    update_generated_message_job_queue_status(
        gm_job_id, GeneratedMessageJobStatus.COMPLETED
    )
    return (True, "Success")


def change_prospect_email_status(
    prospect_email_id: int, status: ProspectEmailStatus, ai_approved: Optional[bool]
):
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect_email.email_status = status
    db.session.add(prospect_email)
    db.session.commit()

    personalized_message_ids = [
        prospect_email.personalized_first_line,
        prospect_email.personalized_subject_line,
        prospect_email.personalized_body,
    ]

    for gm_id in personalized_message_ids:
        if gm_id:
            gm: GeneratedMessage = GeneratedMessage.query.get(gm_id)
            gm.message_status = GeneratedMessageStatus[status.value]

            if ai_approved is not None:
                gm.ai_approved = ai_approved

            db.session.add(gm)
            db.session.commit()

    return True


def clear_prospect_approved_email(prospect_id: int):
    prospect_email: ProspectEmail = ProspectEmail.query.filter(
        ProspectEmail.prospect_id == prospect_id,
        ProspectEmail.email_status == ProspectEmailStatus.APPROVED,
    ).first()
    if prospect_email:
        prospect_email.email_status = ProspectEmailStatus.DRAFT
        db.session.add(prospect_email)
        db.session.commit()

        personalized_message_ids = [
            prospect_email.personalized_first_line,
            prospect_email.personalized_subject_line,
            prospect_email.personalized_body,
        ]

        for gm_id in personalized_message_ids:
            if gm_id:
                gm: GeneratedMessage = GeneratedMessage.query.get(gm_id)
                gm.message_status = GeneratedMessageStatus.DRAFT
                gm.ai_approved = False
                db.session.add(gm)
                db.session.commit()

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_prospect_email_id = None
    db.session.add(prospect)
    db.session.commit()

    return True


def generate_new_email_content_for_approved_email(prospect_id: int):
    """
    Generates new email content for an approved email
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return False, "Prospect not found"
    email_id = prospect.approved_prospect_email_id
    if not email_id:
        return False, "No approved email found"

    email: ProspectEmail = ProspectEmail.query.get(email_id)
    personalized_line = email.personalized_first_line
    gm: GeneratedMessage = GeneratedMessage.query.get(personalized_line)
    old_config_id = gm.stack_ranked_message_generation_configuration_id

    new_config: StackRankedMessageGenerationConfiguration = (
        get_top_stack_ranked_config_ordering(
            generated_message_type=GeneratedMessageType.EMAIL.value,
            prospect_id=prospect_id,
            discluded_config_ids=[old_config_id],
        )
    )
    perms = generate_batch_of_research_points_from_config(
        prospect_id=prospect_id, config=new_config, n=1
    )
    perm = perms[0]
    notes, new_research_points, _ = get_notes_and_points_from_perm(
        perm, cta_id=gm.message_cta
    )
    new_prompt, _ = generate_prompt(prospect_id=prospect_id, notes=notes)

    if new_config:
        new_personalized_line = get_personalized_first_line_from_prompt(
            archetype_id=prospect.archetype_id,
            model_type=GNLPModelType.EMAIL_FIRST_LINE,
            prompt=new_prompt,
            research_points=new_research_points,
            prospect_id=prospect_id,
            outbound_campaign_id=gm.outbound_campaign_id,
            config=new_config,
        )
        email.personalized_first_line = new_personalized_line.id
        db.session.add(email)
        db.session.commit()

        return True, "Success"
    else:
        return False, "No new config(s) found"


def mark_random_new_prospect_email(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_email: ProspectEmail = ProspectEmail.query.filter(
        ProspectEmail.prospect_id == prospect_id,
        ProspectEmail.email_status == ProspectEmailStatus.DRAFT,
        ProspectEmail.id != prospect.approved_prospect_email_id,
    ).first()
    if prospect_email:
        mark_prospect_email_approved(prospect_email.id)

    return True


def mark_prospect_email_approved(prospect_email_id: int):

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect_id = prospect_email.prospect_id

    clear_prospect_approved_email(prospect_id=prospect_id)

    prospect: Prospect = Prospect.query.get(prospect_id)

    if prospect.approved_outreach_message_id:
        clear_prospect_approved_email(prospect_id=prospect_id)

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_prospect_email_id = prospect_email.id
    db.session.add(prospect)
    db.session.commit()

    success = change_prospect_email_status(
        prospect_email_id=prospect_email_id,
        status=ProspectEmailStatus.APPROVED,
        ai_approved=True,
    )

    run_message_rule_engine(message_id=prospect_email.personalized_subject_line)
    run_message_rule_engine(message_id=prospect_email.personalized_body)

    return success


def batch_mark_prospect_email_approved_by_prospect_ids(prospect_ids: list):
    for prospect_id in prospect_ids:
        random_prospect_email: ProspectEmail = ProspectEmail.query.filter(
            ProspectEmail.prospect_id == prospect_id,
        ).first()
        prospect: Prospect = Prospect.query.get(prospect_id)
        if prospect.approved_prospect_email_id:
            continue
        if random_prospect_email:
            mark_prospect_email_approved(random_prospect_email.id)

    return True


def mark_prospect_email_sent(prospect_email_id: int):
    from model_import import ProspectStatus

    prospect: Prospect = Prospect.query.filter(
        Prospect.approved_prospect_email_id == prospect_email_id
    ).first()
    if prospect:
        prospect.status = ProspectStatus.SENT_OUTREACH
        db.session.add(prospect)
        db.session.commit()

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect_email.date_sent = datetime.datetime.now()
    db.session.add(prospect_email)
    db.session.commit()

    return change_prospect_email_status(
        prospect_email_id=prospect_email_id, status=ProspectEmailStatus.SENT
    )


@celery.task
def wipe_prospect_email_and_generations_and_research(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if (
        prospect.status != ProspectStatus.PROSPECTED
        and prospect.approved_prospect_email_id != None
    ):
        return False

    prospect_emails: list = ProspectEmail.query.filter(
        ProspectEmail.prospect_id == prospect_id
    ).all()

    prospect.approved_prospect_email_id = None
    db.session.add(prospect)
    db.session.commit()

    for prospect_email in prospect_emails:
        personalized_line = GeneratedMessage.query.get(
            prospect_email.personalized_first_line
        )
        if (
            not personalized_line
            or personalized_line.message_type != GeneratedMessageType.EMAIL
        ):
            continue
        edits = GeneratedMessageEditRecord.query.filter(
            GeneratedMessageEditRecord.generated_message_id == personalized_line.id
        ).all()
        for edit in edits:
            db.session.delete(edit)
        db.session.commit()
        db.session.delete(personalized_line)
        db.session.delete(prospect_email)
        db.session.commit()

    for prospect_email in prospect_emails:
        personalized_line = GeneratedMessage.query.get(
            prospect_email.personalized_first_line
        )
        if (
            not personalized_line
            or personalized_line.message_type != GeneratedMessageType.EMAIL
        ):
            continue
        db.session.delete(personalized_line)
        db.session.delete(prospect_email)
        db.session.commit()

    messages = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_type == GeneratedMessageType.EMAIL,
        GeneratedMessage.message_status != GeneratedMessageStatus.SENT,
    ).all()
    for message in messages:
        edits = GeneratedMessageEditRecord.query.filter(
            GeneratedMessageEditRecord.generated_message_id == message.id
        ).all()
        for edit in edits:
            db.session.delete(edit)
            db.session.commit()
        db.session.delete(message)
        db.session.commit()

    if prospect.approved_outreach_message_id == None:
        delete_research_points_and_payload_by_prospect_id(prospect_id=prospect_id)

    return True


def batch_approve_message_generations_by_heuristic(prospect_ids: list):
    from src.message_generation.services import (
        approve_message,
    )
    from app import db
    from tqdm import tqdm

    for prospect_id in tqdm(prospect_ids):
        data = db.session.execute(
            """
            select length(completion), *
            from generated_message
            where prospect_id = {prospect_id} and generated_message.message_type = 'LINKEDIN'
            order by abs(270 - length(completion)) asc
            limit 1;
        """.format(
                prospect_id=prospect_id
            )
        ).fetchall()
        if len(data) == 0:
            continue
        data = data[0]
        prospect: Prospect = Prospect.query.get(prospect_id)
        if prospect.approved_outreach_message_id != None:
            continue
        message_id = data["id"]
        approve_message(message_id=message_id)

    return True


def batch_disapprove_message_generations(prospect_ids: int):
    from src.message_generation.services import (
        disapprove_message,
    )
    from app import db
    from tqdm import tqdm

    for prospect_id in tqdm(prospect_ids):
        prospect: Prospect = Prospect.query.get(prospect_id)
        message_id = prospect.approved_outreach_message_id
        disapprove_message(message_id=message_id)

    return True


def create_generated_message_feedback(message_id: int, feedback_value: str):
    feedback: GeneratedMessageFeedback = GeneratedMessageFeedback(
        generated_message_id=message_id, feedback_value=feedback_value
    )
    db.session.add(feedback)
    db.session.commit()

    return True


def generate_cta_examples(company_name: str, persona: str, with_what: str):
    """
    company_name: Name of company
    persona: Name of persona
    with_what: What the company does for persona
    """
    import os

    openai.api_key = os.getenv("OPENAI_KEY")

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=(
            """
Make 6 CTAs that are comma separated for the company.

Example: Curative helps healthcare leaders with getting access to top physicians looking for new opportunities and achieve staffing goals.
Output:
- [Feedback] I wanted to get your thoughts on a staffing solution I'm building for providers - open to chat?
- [Problem] Would love to talk about what issues you're seeing in provider staffing.
- [Priority] Is staffing a priority for your health system? Would love to see if Curative can help.
- [Persona] Since you're a leader in your health system, would love to see if Curative is helpful for staffing.
- [Solution] Given how competitive hiring providers is, and our access to them, would love to connect!
- [Company] Have you heard of Curative? Would love to tell you about how we help with provider staffing.

{company_name} helps {persona} with {with_what}
-
""".format(
                company_name=company_name, persona=persona, with_what=with_what
            )
        ),
        temperature=0,
        max_tokens=500,
        top_p=1,
        frequency_penalty=0.2,
        presence_penalty=0,
    )

    ctas = []

    options = response["choices"][0]["text"].split("\n")
    for option in options:
        tag, cta = option.split("] ")
        tag = tag[1:]

        ctas.append({"tag": tag, "cta": cta})

    return ctas


def get_named_entities(string: str):
    """Get named entities from a string (completion message)

    We use the OpenAI davinci-03 completion model to generate the named entities.
    """
    if string == "":
        return []

    # Unlikely to have more than 50 tokens (words)
    max_tokens_length = 50
    message = string.strip()
    instruction = "instruction: Return a list of all named entities, including persons's names, separated by ' // '. If no entities are detected, return 'NONE'."

    fewshot_1_message = "message: Hey David, I really like your background in computer security. I also really enjoyed reading the recommendation Aakash left for you. Impressive since you've been in the industry for 9+ years! You must have had a collection of amazing work experiences, given that you've been with Gusto, Naropa University, and Stratosphere in the past."
    fewshot_1_entities = (
        "entities: David // Aakash // Gusto // Naropa University // Stratosphere"
    )
    fewshot_1 = fewshot_1_message + "\n\n" + instruction + "\n\n" + fewshot_1_entities

    fewshot_2_message = "message: I'd like to commend you for being in the industry for 16+ years. That is no small feat!"
    fewshot_2_entities = "entities: NONE"
    fewshot_2 = fewshot_2_message + "\n\n" + instruction + "\n\n" + fewshot_2_entities

    target = "message: " + message + "\n\n" + instruction + "\n\n" + "entities:"

    prompt = fewshot_1 + "\n\n--\n\n" + fewshot_2 + "\n\n--\n\n" + target

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=max_tokens_length,
        temperature=0,
    )
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return []

    choices = response["choices"]
    top_choice = choices[0]
    entities_dirty = top_choice["text"].strip()
    entities_clean = entities_dirty.replace("\n", "").split(" // ")

    # OpenAI returns "NONE" if there are no entities
    if len(entities_clean) == 1 and entities_clean[0] == "NONE":
        return []

    return entities_clean


def get_named_entities_for_generated_message(message_id: int):
    """Get named entities for a generated message"""
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    entities = get_named_entities(message.completion)

    return entities


def run_check_message_has_bad_entities(message_id: int):
    """Check if the message has any entities that are not in the prompt

    If there are any entities that are not in the prompt, we flag the message and include the unknown entities.
    """

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    cta_id = message.message_cta
    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)

    entities = get_named_entities_for_generated_message(message_id=message_id)

    prompt = message.prompt
    sanitized_prompt = re.sub(
        "[^0-9a-zA-Z]+",
        " ",
        prompt.lower(),
    ).strip()

    if cta is not None:
        cta_text = cta.text_value
    else:
        cta_text = prompt
    sanitized_cta_text = re.sub(
        "[^0-9a-zA-Z]+",
        " ",
        cta_text.lower(),
    ).strip()

    flagged_entities = []
    for entity in entities:
        for exception in ner_exceptions:
            if exception in entity:
                entity = entity.replace(exception, "").strip()

        if entity.lower() in title_abbreviations:  # Abbreviated titles are OK
            full_title = title_abbreviations[entity.lower()]
            if full_title in prompt.lower():
                continue

        sanitized_entity = re.sub(
            "[^0-9a-zA-Z]+",
            " ",
            entity.lower(),
        ).strip()

        if (
            sanitized_entity not in sanitized_prompt
            and sanitized_entity not in sanitized_cta_text
        ):
            flagged_entities.append(entity)

    generated_message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    generated_message.unknown_named_entities = flagged_entities
    db.session.add(generated_message)
    db.session.commit()

    return len(flagged_entities) > 0, flagged_entities


def clear_all_generated_message_jobs():
    gm_jobs: list = GeneratedMessageJob.query.all()
    for gm_job in gm_jobs:
        db.session.delete(gm_job)
        db.session.commit()
    return True


def batch_update_generated_message_ctas(payload: dict):
    """
    Update the active status of a batch of generated message CTAs

    payload looks like:
    [{"id":93,"text_value":"As a finance leader, how are you placing controls on company spend ? Would love to show you how Ramp can help.","active":false,"archetype_id":31,"archetype":"(Tim) CFOs at SaaS companies 11-500 FTE","prospects":"42","accepted_prospects":"4","accepted_percent":0.09523809523809523,"array_agg":["Tim Signorile"]}]
    """
    for cta in payload:
        cta_id = cta["id"]
        cta_active = cta["active"]

        generated_message_cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(
            cta_id
        )
        generated_message_cta.active = cta_active
        db.session.add(generated_message_cta)
        db.session.commit()

    return True


def get_generation_statuses(campaign_id: int) -> dict:
    """Gets the statuses of the generation jobs for a campaign

    Args:
        campaign_id (int): The ID of the campaign to get the statuses for

    Returns:
        dict: A dictionary containing different generation_statuses
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        return {}

    # Statistics
    total_job_count = 0
    statuses_count = {}
    for job_status in GeneratedMessageJobStatus:
        statuses_count[job_status.value] = 0
    jobs_list = []

    # Get generation jobs
    generation_jobs: list[
        GeneratedMessageJobQueue
    ] = GeneratedMessageJobQueue.query.filter(
        GeneratedMessageJobQueue.outbound_campaign_id == campaign_id,
    ).all()

    # Add job to statistics
    for job in tqdm(generation_jobs):
        jobs_list.append(job.to_dict())
        status: GeneratedMessageJobStatus = job.status
        if status.value not in statuses_count:
            statuses_count[status.value] = 0
        statuses_count[status.value] += 1
        total_job_count += 1

    return {
        "total_job_count": total_job_count,
        "statuses_count": statuses_count,
        "jobs_list": jobs_list,
    }


@celery.task(bind=True, max_retries=2)
def wipe_message_generation_job_queue(self, campaign_id: int) -> tuple[bool, str]:
    """Wipes the message generation job queue for a campaign

    Args:
        campaign_id (int): The ID of the campaign to wipe the queue for
        client_sdr_id (int): The ID of the client SDR

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a string with a message
    """
    try:
        campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
        if not campaign:
            return False, "Campaign does not exist"

        # Get the prospects in this campaign
        prospect_ids = campaign.prospect_ids

        # Get the generation job
        for prospect_id in prospect_ids:
            generation_job: GeneratedMessageJobQueue = (
                GeneratedMessageJobQueue.query.filter(
                    GeneratedMessageJobQueue.prospect_id == prospect_id,
                    GeneratedMessageJobQueue.outbound_campaign_id == campaign_id,
                ).first()
            )

            # If there is no generation job, we can't get the status
            if not generation_job:
                continue

            # Delete the job
            db.session.delete(generation_job)
            db.session.commit()

        return True, "Successfully wiped the queue"
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def manually_mark_ai_approve(
    generated_message_id: int, new_ai_approve_status: bool
) -> bool:
    """Marks a GeneratedMessage.ai_approved as a specified value, manually.

    Should be used by UW.

    Args:
        generated_message_id (int): ID of the GeneratedMessage to approve.
        new_ai_approve_status (bool): New value for GeneratedMessage.ai_approved.

    Returns:
        bool: True if successful, False if not.
    """
    try:
        gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
        if not gm:
            return False
        gm.ai_approved = new_ai_approve_status
        db.session.add(gm)
        db.session.commit()
        return True
    except:
        db.session.rollback()
        return False
