import email
import traceback

from src.bump_framework.models import BumpFrameworkTemplates
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.li_conversation.models import (
    LinkedInConvoMessage,
    LinkedinInitialMessageTemplate,
)
from src.message_generation.models import (
    GeneratedMessageAutoBump,
    GeneratedMessageCTAToAssetMapping,
    GeneratedMessageEmailType,
    SendStatus,
)
from src.ml.ai_researcher_services import run_ai_personalizer_on_prospect_email
from src.ml.services import (
    determine_best_bump_framework_from_convo,
    get_text_generation,
)
from src.client.models import ClientAssets, ClientSDR
from src.research.account_research import generate_prospect_research
from src.message_generation.models import GeneratedMessageQueue
from sqlalchemy import nullslast, or_
from sqlalchemy import text
from sqlalchemy.sql.expression import func
from src.ml.openai_wrappers import (
    wrapped_create_completion,
    OPENAI_COMPLETION_DAVINCI_3_MODEL,
)
from model_import import (
    PLGProductLeads,
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
    LinkedinConversationEntry,
    EmailConversationMessage,
    AccountResearchPoints,
    BumpFramework,
)
from typing import List, Optional, Union
from src.ml.rule_engine import run_message_rule_engine
from src.ml_adversary.services import run_adversary
from src.email_outbound.models import ProspectEmailStatus
from src.research.models import ResearchPayload, ResearchPoints
from src.utils.random_string import generate_random_alphanumeric
from src.research.linkedin.services import get_research_and_bullet_points_new
from model_import import Prospect, ProspectOverallStatus
from ..ml.fine_tuned_models import (
    get_config_completion,
    get_few_shot_baseline_prompt,
)
from src.utils.random_string import generate_random_alphanumeric
from src.email_outbound.services import create_prospect_email
from src.message_generation.ner_exceptions import ner_exceptions, title_abbreviations
from ..utils.abstract.attr_utils import deep_get
import random
from sqlalchemy import or_
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
from src.utils.slack import URL_MAP, send_slack_message
from src.prospecting.services import *
from model_import import Prospect, ResearchPoints, ResearchPayload
from app import db
from src.ml.openai_wrappers import *


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
            Prospect.icp_fit_score.label("icp_fit_score"),
            Prospect.icp_fit_reason.label("icp_fit_reason"),
            Prospect.title.label("title"),
            Prospect.company.label("company"),
            Prospect.img_url.label("img_url"),
            ClientArchetype.archetype.label("archetype"),
            GeneratedMessage.id.label("message_id"),
            GeneratedMessage.completion.label("completion"),
            GeneratedMessage.created_at.label("created_at"),
        )
        .join(
            GeneratedMessage,
            Prospect.approved_outreach_message_id == GeneratedMessage.id,
        )
        .join(
            ClientArchetype,
            ClientArchetype.id == Prospect.archetype_id,
        )
        .outerjoin(
            OutboundCampaign,
            OutboundCampaign.id == GeneratedMessage.outbound_campaign_id,
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
        joined_prospect_message.order_by(OutboundCampaign.priority_rating.desc())
        .order_by(nullslast(GeneratedMessage.priority_rating.desc()))
        .order_by(nullslast(Prospect.icp_fit_score.desc()))
        .order_by(nullslast(GeneratedMessage.created_at.desc()))
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
                "icp_fit_score": row.icp_fit_score,
                "icp_fit_reason": row.icp_fit_reason,
                "archetype": row.archetype,
                "created_at": row.created_at,
            }
        )

    return message_list, total_count


@celery.task(bind=True, max_retries=3)
def generate_outreaches_for_prospect_list_from_multiple_ctas(
    self, prospect_ids: list, cta_ids: list, outbound_campaign_id: int
):
    try:
        for i, prospect_id in enumerate(prospect_ids):
            cta_id = cta_ids[i % len(cta_ids)] if len(cta_ids) > 0 else None

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
                generated_message_cta_id=cta_id,
                attempts=0,
                generated_message_type=GeneratedMessageType.LINKEDIN,
            )
            db.session.add(gm_job)
            db.session.commit()

            # Research and generate outreaches for the prospect
            # research_and_generate_outreaches_for_prospect.apply_async(
            #     [
            #         prospect_id,
            #         outbound_campaign_id,
            #         cta_id,
            #         gm_job.id,
            #     ],
            #     countdown=i * 10,
            #     queue="message_generation",
            #     routing_key="message_generation",
            #     priority=10,
            # )
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task
def run_queued_gm_job():
    data = db.session.execute(
        """
        select
            prospect_id,
            outbound_campaign_id,
            generated_message_cta_id as cta_id,
            generated_message_job_queue.id as gm_job_id,
            generated_message_job_queue.generated_message_type
        from generated_message_job_queue
        join prospect on generated_message_job_queue.prospect_id = prospect.id
        join client_archetype on prospect.archetype_id = client_archetype.id
        where
            generated_message_job_queue.created_at > NOW() - '1 days'::INTERVAL and
            generated_message_job_queue.status = 'PENDING' and
            (
                (generated_message_job_queue.generated_message_type = 'LINKEDIN' and (generated_message_cta_id is not null or client_archetype.template_mode = true))
                or
                (generated_message_job_queue.generated_message_type = 'EMAIL')
            ) and
            attempts < 3
        order by random()
        limit 3;
    """
    ).fetchall()

    for row in data:
        prospect_id = row[0]
        outbound_campaign_id = row[1]
        cta_id = row[2]
        gm_job_id = row[3]
        generated_message_type = row[4]

        if generated_message_type == GeneratedMessageType.LINKEDIN.value:
            # Research and generate outreaches for the prospect
            research_and_generate_outreaches_for_prospect.apply_async(
                [
                    prospect_id,
                    outbound_campaign_id,
                    cta_id,
                    gm_job_id,
                ],
                queue="message_generation",
                routing_key="message_generation",
                priority=10,
            )
        elif generated_message_type == GeneratedMessageType.EMAIL.value:
            # Research and generate outreaches for the prospect
            generate_prospect_email.apply_async(
                args=[prospect_id, outbound_campaign_id, gm_job_id],
                queue="message_generation",
                routing_key="message_generation",
                priority=10,
            )


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
def research_and_generate_outreaches_for_prospect(  # THIS IS A PROTECTED TASK. DO NOT CHANGE THE NAME OF THIS FUNCTION
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
        # batch_approve_message_generations_by_heuristic(prospect_ids=[prospect_id])

        # Mark the job as completed
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.COMPLETED
        )
    except Exception as e:
        db.session.rollback()
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.FAILED, error_message=str(e)
        )
        raise self.retry(exc=e, countdown=10**self.request.retries)


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

        # if "CUSTOM" in [x.research_point_type for x in points]:
        #     custom_point = [x for x in points if x.research_point_type == "CUSTOM"][0]
        #     if custom_point not in sample:
        #         sample.append(custom_point)

    return perms


def generate_batch_of_research_points_from_config(
    prospect_id: int,
    config: Optional[StackRankedMessageGenerationConfiguration],
    n: int = 1,
):
    all_research_points: list = ResearchPoints.get_research_points_by_prospect_id(
        prospect_id=prospect_id
    )
    prospect: Prospect = Prospect.query.get(prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    transformer_blocklist_initial_values = (
        [x for x in archetype.transformer_blocklist_initial]
        if archetype.transformer_blocklist_initial
        else []
    )
    allowed_research_point_types_in_config = (
        [
            x.research_point_type
            for x in all_research_points
            if x.research_point_type not in transformer_blocklist_initial_values
        ]
        if all_research_points
        else []
    )

    # If there are no research points, return an empty list
    if not all_research_points or len(all_research_points) == 0:
        return []

    if not config:
        return generate_batches_of_research_points(
            points=all_research_points, n=n, num_per_perm=2
        )

    # Remove the research point types that are in the blocklists
    research_points = [
        x
        for x in all_research_points
        if x.research_point_type in allowed_research_point_types_in_config
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
    from src.li_conversation.services import ai_initial_li_msg_prompt

    campaign: OutboundCampaign = OutboundCampaign.query.get(outbound_campaign_id)

    ### Use new template-based generation ###
    prospect: Prospect = Prospect.query.get(prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    if archetype.template_mode:
        template: LinkedinInitialMessageTemplate = (
            LinkedinInitialMessageTemplate.get_random(prospect.archetype_id)
        )

        prompt = ai_initial_li_msg_prompt(
            client_sdr_id=prospect.client_sdr_id,
            prospect_id=prospect_id,
            template=template.message,
            additional_instructions=template.additional_instructions or "",
            research_points=template.research_points or [],
        )

        completion = get_text_generation(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            model="gpt-4",
            type="LI_MSG_INIT",
            prospect_id=prospect_id,
            client_sdr_id=prospect.client_sdr_id,
            use_cache=False,
        )

        message: GeneratedMessage = GeneratedMessage(
            prospect_id=prospect_id,
            research_points=None,
            prompt=prompt,
            completion=completion,
            message_status=GeneratedMessageStatus.DRAFT,
            outbound_campaign_id=outbound_campaign_id,
            adversarial_ai_prediction=False,
            message_cta=None,
            message_type=GeneratedMessageType.LINKEDIN,
            few_shot_prompt=None,
            stack_ranked_message_generation_configuration_id=None,
            priority_rating=campaign.priority_rating if campaign else 0,
            li_init_template_id=template.id,
        )
        db.session.add(message)
        db.session.commit()

        approve_message(message_id=message.id)

        return [completion]

    ### Use legacy CTA + Voice generation ###
    NUM_GENERATIONS = 1
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
            return []
            # raise ValueError("No research point permutations")

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
                stack_ranked_message_generation_configuration_id=(
                    TOP_CONFIGURATION.id if TOP_CONFIGURATION else None
                ),
                priority_rating=campaign.priority_rating if campaign else 0,
            )
            db.session.add(message)
            db.session.commit()

            approve_message(message_id=message.id)

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

    campaign: OutboundCampaign = OutboundCampaign.query.get(outbound_campaign_id)

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
            completions = get_few_shot_baseline_prompt(prompt=prompt)
            instruction_id = None
            few_shot_prompt = None
        else:
            (
                completions,
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
                priority_rating=campaign.priority_rating if campaign else 0,
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

    db.session.add(message)

    message_id = message.id

    prospect_id = message.prospect_id
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = message.id
    db.session.add(prospect)
    db.session.commit()

    run_message_rule_engine(message_id=message_id)

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)

    # If the message has no problems, mark it as "human approved"
    if not message.blocking_problems or len(message.blocking_problems) == 0:
        message.ai_approved = True
        db.session.commit()
    else:
        message.ai_approved = False
        db.session.commit()

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
        text(
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
        )
    ).fetchall()
    ids = [x["id"] for x in data]
    new_index = (ids.index(message_id) + 1) % len(ids)
    new_message_id = ids[new_index]
    approve_message(message_id=new_message_id)

    return True


def delete_message_generation_by_prospect_id(prospect_id: int):
    from model_import import GeneratedMessage

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = None
    db.session.add(prospect)
    db.session.commit()

    messages: list = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_type == GeneratedMessageType.LINKEDIN,
    ).all()

    for message in messages:
        linkedin_conversation_entries: list[LinkedinConversationEntry] = (
            LinkedinConversationEntry.query.filter(
                LinkedinConversationEntry.initial_message_id == message.id
            ).all()
        )
        for entry in linkedin_conversation_entries:
            db.session.delete(entry)
            db.session.commit()

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


def create_cta(
    archetype_id: int,
    text_value: str,
    expiration_date: Optional[datetime],
    active: bool = True,
    cta_type: str = "Manual",
    auto_mark_as_scheduling_on_acceptance: Optional[bool] = False,
    asset_ids: list[int] = [],
):
    # duplicate_cta_exists = GeneratedMessageCTA.query.filter(
    #     GeneratedMessageCTA.archetype_id == archetype_id,
    #     GeneratedMessageCTA.text_value == text_value,
    # ).first()
    # if duplicate_cta_exists:
    #     return duplicate_cta_exists

    cta: GeneratedMessageCTA = GeneratedMessageCTA(
        archetype_id=archetype_id,
        text_value=text_value,
        active=active,
        expiration_date=expiration_date,
        cta_type=cta_type,
        auto_mark_as_scheduling_on_acceptance=auto_mark_as_scheduling_on_acceptance,
    )
    db.session.add(cta)
    db.session.commit()

    cta_id = cta.id

    for asset_id in asset_ids:
        mapping = GeneratedMessageCTAToAssetMapping(
            generated_message_cta_id=cta_id, client_assets_id=asset_id
        )
        db.session.add(mapping)
    db.session.commit()

    return cta


def backfill_cta_types():
    "Predicts the type of call-to-action based on the text value."
    entries = db.session.execute(
        """
        select
            generated_message_cta.id,
            generated_message_cta.text_value,
            case
                when generated_message_cta.text_value ilike '%the area%' or generated_message_cta.text_value ilike '%coffee%' or generated_message_cta.text_value ilike '%lunch%' or generated_message_cta.text_value ilike '%meet at%' then 'In-Person-based'
                when generated_message_cta.text_value ilike '%helpful%' then 'Help-Based'
                when generated_message_cta.text_value ilike '%your thoughts%' then 'Feedback-Based'
                when generated_message_cta.text_value ilike '%what issues%' then 'Problem-Based'
                when generated_message_cta.text_value ilike '%priority%' then 'Priority-Based'
                when generated_message_cta.text_value ilike '%since you%re a%' then 'Persona-Based'
                when generated_message_cta.text_value ilike '%given how%' and generated_message_cta.text_value ilike '%solution%' then 'Solution-Based'
                when generated_message_cta.text_value ilike '%have you heard of%' then 'Company-Based'
                when generated_message_cta.text_value ilike '%recently%' then 'Time-Based'
                when generated_message_cta.text_value ilike '%demo of%' then 'Demo-Based'
                when generated_message_cta.text_value ilike '%interested%' then 'Interest-Based'
                when generated_message_cta.text_value ilike '%testing%' or generated_message_cta.text_value ilike '%test %' then 'Test-Based'
                when generated_message_cta.text_value ilike '%? %' then 'Question-Based'
                when generated_message_cta.text_value ilike '%expert%' then 'Expertise-Based'
                when generated_message_cta.text_value ilike '%minutes%' then 'Meeting-Based'
                when generated_message_cta.text_value ilike '%best person%' then 'Persona-Based'
                when generated_message_cta.text_value ilike '%competitive%' or generated_message_cta.text_value ilike '%roadblock%' or generated_message_cta.text_value ilike '%given the%' then 'Pain-Based'
                when generated_message_cta.text_value ilike '%we work with%' or generated_message_cta.text_value ilike '%you%re a%' then 'Persona-Based'
                when generated_message_cta.text_value ilike '%others%' then 'FOMO-Based'
                when generated_message_cta.text_value ilike '%benchmark%' then 'Competitor-Based'
                when generated_message_cta.text_value ilike '%learn%' or generated_message_cta.text_value ilike '%strategy%' then 'Discovery-Based'
                when generated_message_cta.text_value ilike '%looking%' then 'Intent-Based'
                when generated_message_cta.text_value ilike '%chat%' or generated_message_cta.text_value ilike '%call %' then 'Meeting-Based'
                when generated_message_cta.text_value ilike '%\%%' then 'Result-Based'
                when generated_message_cta.text_value ilike '%you %' then 'Role-Based'
                when generated_message_cta.text_value ilike '%issues %' then 'Pain-Based'
                when generated_message_cta.text_value ilike '%check out %' then 'Demo-Based'
                when generated_message_cta.text_value ilike '%collab %' then 'Partner-Based'
                when generated_message_cta.text_value ilike '%partner %' then 'Partner-Based'
                when generated_message_cta.text_value ilike '%how %' then 'Solution-Based'
                when generated_message_cta.text_value ilike '%resource %' then 'Resource-Based'
                when generated_message_cta.text_value ilike '%feedback%' then 'Feedback-Based'
                when generated_message_cta.text_value ilike '% need%' then 'Priority-Based'
                when generated_message_cta.text_value ilike '% has worked%' then 'FOMO-Based'
                when generated_message_cta.text_value ilike '%worked%' then 'FOMO-Based'
                when generated_message_cta.text_value ilike '%enable%' then 'FOMO-Based'
                when generated_message_cta.text_value ilike '%good fit%' then 'Company-Based'
                when generated_message_cta.text_value ilike '%I can%' then 'Help-Based'
                when generated_message_cta.text_value ilike '%event%' or generated_message_cta.text_value ilike '%panel%' then 'Event-Based'
                when generated_message_cta.text_value ilike '%Hmmmm%' then 'Test-Based'
                when generated_message_cta.text_value ilike '%explore%' then 'Partner-Based'
                when generated_message_cta.text_value ilike '%a fit%' then 'Company-Based'
                when generated_message_cta.text_value ilike '%useful%' then 'Feedback-Based'
                when generated_message_cta.text_value ilike '%open to%' then 'Role-Based'
                when generated_message_cta.text_value ilike '%connect%' then 'Connection-Based'
                when generated_message_cta.text_value ilike '%connect%' then 'Connection-Based'
                when generated_message_cta.text_value ilike '%consider%' then 'Feedback-Based'
                when generated_message_cta.text_value ilike '%perspective%' then 'Feedback-Based'
                when generated_message_cta.text_value ilike '%resource%' then 'Help-Based'
                when generated_message_cta.text_value ilike '%goals%' then 'Priority-Based'
                when generated_message_cta.text_value ilike '%your time%' then 'Priority-Based'
                when generated_message_cta.text_value ilike '%grow%' then 'Priority-Based'
                when generated_message_cta.text_value ilike '%sample%' or generated_message_cta.text_value ilike '%wddwdwdwdw%' or generated_message_cta.text_value ilike '%wd d wdwdw w dwd w d%' or generated_message_cta.text_value ilike '%dwwddwdwdw%' then 'Test-Based'

                when generated_message_cta.text_value ilike '%?%' then 'Question-Based'
            else ''
            end label
        from generated_message_cta
        order by 2 asc;
    """
    ).fetchall()

    for entry in tqdm(entries):
        id = entry["id"]
        label = entry["label"]

        gm: GeneratedMessageCTA = GeneratedMessageCTA.query.get(entry["id"])
        print(gm.text_value, label)
        if gm and gm.cta_type != label:
            gm.cta_type = label
            db.session.add(gm)
            db.session.commit()


def update_cta(
    cta_id: int,
    text_value: str,
    expiration_date: Optional[datetime],
    auto_mark_as_scheduling_on_acceptance: Optional[bool] = None,
    cta_type: Optional[str] = None,
):
    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)
    if not cta:
        return False

    cta.text_value = text_value
    if expiration_date:
        cta.expiration_date = expiration_date

    if auto_mark_as_scheduling_on_acceptance != None:
        cta.auto_mark_as_scheduling_on_acceptance = (
            auto_mark_as_scheduling_on_acceptance
        )

    if cta_type:
        cta.cta_type = cta_type

    db.session.add(cta)
    db.session.commit()

    return True


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


def is_cta_active(cta_id: int):
    from model_import import GeneratedMessageCTA

    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)
    if cta.expiration_date and cta.expiration_date < datetime.utcnow():
        if cta.active:
            cta.active = False
            db.session.add(cta)
            db.session.commit()

            archetype: ClientArchetype = ClientArchetype.query.get(cta.archetype_id)
            sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)

            send_slack_message(
                message=f"CTA #{cta_id} has expired and is now inactive.\n*CTA:* {cta.text_value}\n*SDR:* {sdr.name}\n*Archetype:* {archetype.archetype}\n*Expiration Date:* {cta.expiration_date}",
                webhook_urls=[URL_MAP["csm-notifications-cta-expired"]],
            )

        return False
    return cta.active


def toggle_cta_active(cta_id: int):
    from model_import import GeneratedMessageCTA

    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)
    cta.active = not cta.active
    db.session.add(cta)
    db.session.commit()

    return True


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
                generated_message_type=GeneratedMessageType.EMAIL,
            )
            db.session.add(gm_job)
            db.session.commit()

            # Generate the prospect email
            # generate_prospect_email.apply_async(
            #     args=[prospect_id, campaign_id, gm_job.id],
            #     countdown=i * 10,
            #     queue="message_generation",
            #     routing_key="message_generation",
            #     priority=10,
            # )
    except Exception as e:
        print(e)
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3)
def generate_prospect_email(  # THIS IS A PROTECTED TASK. DO NOT CHANGE THE NAME OF THIS FUNCTION
    self, prospect_id: int, campaign_id: int, gm_job_id: int
) -> tuple[bool, str]:
    from src.message_generation.email.services import (
        ai_initial_email_prompt,
        ai_subject_line_prompt,
        generate_email,
        generate_subject_line,
    )

    try:
        campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)

        # 1. Mark the job as in progress
        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.IN_PROGRESS
        )

        # 2. Increment the attempts
        increment_generated_message_job_queue_attempts(gm_job_id)

        # 3. Check if the prospect exists
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
        ai_personalization_enabled = client_archetype.is_ai_research_personalization_enabled
        client_sdr_id = prospect.client_sdr_id
        if not prospect:
            update_generated_message_job_queue_status(
                gm_job_id,
                GeneratedMessageJobStatus.FAILED,
                error_message="Prospect does not exist",
            )
            return (False, "Prospect does not exist")

        # 4. Check if the prospect already has a prospect_email
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

        # 5. Perform account research (double down)
        generate_prospect_research(prospect.id, False, False)

        # 6. Create research points and payload for the prospect
        get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

        # 7a. Get the Email Body prompt
        template_id = None
        templates: list[EmailSequenceStep] = EmailSequenceStep.query.filter(
            EmailSequenceStep.client_archetype_id == prospect.archetype_id,
            EmailSequenceStep.overall_status == ProspectOverallStatus.PROSPECTED,
            EmailSequenceStep.active == True,
        ).all()
        template: EmailSequenceStep = random.choice(templates) if templates else None
        if template:
            template_id = template.id
        initial_email_prompt = ai_initial_email_prompt(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            template_id=template_id,
        )
        # 7b. Generate the email body
        email_body = generate_email(prompt=initial_email_prompt)
        email_body = email_body.get("body")

        # 8a. Get the Subject Line
        subjectline_template_id = None
        subjectline_strict = False  # Tracks if we need to use AI generate. [[ and {{ in template signify AI hence not strict
        subjectline_templates: list[
            EmailSubjectLineTemplate
        ] = EmailSubjectLineTemplate.query.filter(
            EmailSubjectLineTemplate.client_archetype_id == prospect.archetype_id,
            EmailSubjectLineTemplate.active == True,
        ).all()
        subjectline_template: EmailSubjectLineTemplate = (
            random.choice(subjectline_templates) if subjectline_templates else None
        )
        if subjectline_template:
            subjectline_template_id = subjectline_template.id
            subjectline_strict = (
                "[[" not in subjectline_template.subject_line
                and "{{" not in subjectline_template.subject_line
            )

        # 8b. Generate the subject line
        if subjectline_strict:
            subject_line_prompt = "No AI template detected in subject line template. Using exact template."
            subject_line = subjectline_template.subject_line
        else:
            subject_line_prompt = ai_subject_line_prompt(
                client_sdr_id=client_sdr_id,
                prospect_id=prospect_id,
                email_body=email_body,
                subject_line_template_id=subjectline_template.id,
            )
            # 7b. Generate the email body
            email_body = generate_email(prompt=initial_email_prompt)
            email_body = email_body.get("body")

            # 8a. Get the Subject Line
            subjectline_template_id = None
            # Tracks if we need to use AI generate. [[ and {{ in template signify AI hence not strict
            subjectline_strict = False
            subjectline_templates: list[
                EmailSubjectLineTemplate
            ] = EmailSubjectLineTemplate.query.filter(
                EmailSubjectLineTemplate.client_archetype_id == prospect.archetype_id,
                EmailSubjectLineTemplate.active == True,
            ).all()
            subjectline_template: EmailSubjectLineTemplate = random.choice(
                subjectline_templates
            )
            if subjectline_template:
                subjectline_template_id = subjectline_template.id
                subjectline_strict = (
                    "[[" not in subjectline_template.subject_line
                    and "{{" not in subjectline_template.subject_line
                )

            # 8b. Generate the subject line
            subject_line = generate_subject_line(prompt=subject_line_prompt)
            subject_line = subject_line.get("subject_line")

        # 9. Create the GeneratedMessage objects
        ai_generated_body: GeneratedMessage = GeneratedMessage(
            prospect_id=prospect_id,
            outbound_campaign_id=campaign_id,
            prompt=initial_email_prompt,
            completion=email_body,
            message_status=GeneratedMessageStatus.DRAFT,
            message_type=GeneratedMessageType.EMAIL,
            priority_rating=campaign.priority_rating if campaign else 0,
            email_type=GeneratedMessageEmailType.BODY,
            email_sequence_step_template_id=template_id,
        )
        ai_generated_subject_line = GeneratedMessage(
            prospect_id=prospect_id,
            outbound_campaign_id=campaign_id,
            prompt=subject_line_prompt,
            completion=subject_line,
            message_status=GeneratedMessageStatus.DRAFT,
            message_type=GeneratedMessageType.EMAIL,
            priority_rating=campaign.priority_rating if campaign else 0,
            email_type=GeneratedMessageEmailType.SUBJECT_LINE,
            email_subject_line_template_id=subjectline_template_id,
        )
        db.session.add(ai_generated_body)
        db.session.add(ai_generated_subject_line)
        db.session.commit()

        # 9b. Run rule engine on the subject line and body
        # TODO(Aakash) - commented out rule engine since these are configured for
        #                   linkedin messages - not email subject lines / bodies
        #                   replace with engine for email subject lines / bodies
        # run_message_rule_engine(message_id=ai_generated_subject_line.id)
        # run_message_rule_engine(message_id=ai_generated_body.id)

        # 10. Create the ProspectEmail object
        prospect_email: ProspectEmail = create_prospect_email(
            prospect_id=prospect_id,
            personalized_subject_line_id=ai_generated_subject_line.id,
            personalized_body_id=ai_generated_body.id,
            outbound_campaign_id=campaign_id,
        )

        if ai_personalization_enabled:
            # 10.a. Run AI personalizer on the email body and subject line if enabled
            run_ai_personalizer_on_prospect_email(prospect_email.id)

        # 11. Save the prospect_email_id to the prospect and mark the prospect_email as approved
        # This also runs rule_engine on the email body and first line
        mark_prospect_email_approved(
            prospect_email_id=prospect_email.id,
        )
    except Exception as e:
        db.session.rollback()
        tb = traceback.format_exc()

        update_generated_message_job_queue_status(
            gm_job_id, GeneratedMessageJobStatus.FAILED, tb
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)

    update_generated_message_job_queue_status(
        gm_job_id, GeneratedMessageJobStatus.COMPLETED
    )
    return (True, "Success")


def change_prospect_email_status(
    prospect_email_id: int,
    status: ProspectEmailStatus,
    ai_approved: Optional[bool] = False,
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


def regenerate_email_body(
    # client_sdr_id: int,
    prospect_id: int,
) -> tuple[bool, str]:
    """Regenerates the email body for a prospect

    Args:
        client_sdr_id (int): The ID of the client sdr
        prospect_id (int): The ID of the prospect

    Returns:
        tuple[bool, str]: A tuple containing a boolean representing success and a string representing the message
    """
    # Get the Prospect Email
    prospect: Prospect = Prospect.query.get(prospect_id)
    # if prospect.client_sdr_id != client_sdr_id:
    #     return False, "Client SDR does not match prospect's client SDR"
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    if not prospect_email:
        return False, "No prospect email found"

    # Get the personalized body
    personalized_body: GeneratedMessage = GeneratedMessage.query.get(
        prospect_email.personalized_body
    )
    if not personalized_body:
        return False, "No personalized body found"

    # Get the prompt
    prompt = personalized_body.prompt

    # Generate the email
    email_body = generate_email(prompt=prompt)
    email_body = email_body.get("body")

    # Update the GeneratedMessage
    personalized_body.completion = email_body
    personalized_body.message_status = GeneratedMessageStatus.DRAFT
    db.session.commit()

    # Run Rule Engine + ARREE
    run_message_rule_engine(personalized_body.id)

    return True, "Success"


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


def mark_prospect_email_approved(prospect_email_id: int, ai_approved: bool = False):
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect_id = prospect_email.prospect_id

    clear_prospect_approved_email(prospect_id=prospect_id)

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_prospect_email_id = prospect_email.id
    db.session.add(prospect)
    db.session.commit()

    problems_subject_line = run_message_rule_engine(
        message_id=prospect_email.personalized_subject_line
    )
    problems_email_body = run_message_rule_engine(
        message_id=prospect_email.personalized_body
    )

    success = change_prospect_email_status(
        prospect_email_id=prospect_email_id,
        status=ProspectEmailStatus.APPROVED,
        ai_approved=ai_approved
        or (len(problems_subject_line) == 0 and len(problems_email_body) == 0),
    )

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
    prospect_email.date_sent = datetime.now()
    db.session.add(prospect_email)
    db.session.commit()

    return change_prospect_email_status(
        prospect_email_id=prospect_email_id,
        status=ProspectEmailStatus.SENT,
        ai_approved=True,
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
            text(
                """
            select length(completion), *
            from generated_message
            where prospect_id = {prospect_id} and generated_message.message_type = 'LINKEDIN'
            order by abs(270 - length(completion)) asc
            limit 1;
        """.format(
                    prospect_id=prospect_id
                )
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

    text = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": (
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
            },
        ],
        temperature=0,
        max_tokens=500,
        top_p=1,
        frequency_penalty=0.2,
    )

    ctas = []

    options = text.split("\n")
    for option in options:
        tag, cta = option.split("] ")
        tag = tag[1:]

        ctas.append({"tag": tag, "cta": cta})

    return ctas


# DEPRECATED [2024-03-26]: This NER function is deprecated and replaced by detect_hallucinations
# def get_named_entities(string: str):
#     """Get named entities from a string (completion message)

#     We use the OpenAI davinci-03 completion model to generate the named entities.
#     """
#     if string == "":
#         return []

#     # Unlikely to have more than 50 tokens (words)
#     max_tokens_length = 50
#     message = string.strip()
#     instruction = "instruction: Return a list of all named entities, including persons's names, separated by ' // '. If no entities are detected, return 'NONE'."

#     fewshot_1_message = "message: Hey David, I really like your background in computer security. I also really enjoyed reading the recommendation Aakash left for you. Impressive since you've been in the industry for 9+ years! You must have had a collection of amazing work experiences, given that you've been with Gusto, Naropa University, and Stratosphere in the past."
#     fewshot_1_entities = (
#         "entities: David // Aakash // Gusto // Naropa University // Stratosphere"
#     )
#     fewshot_1 = fewshot_1_message + "\n\n" + instruction + "\n\n" + fewshot_1_entities

#     fewshot_2_message = "message: I'd like to commend you for being in the industry for 16+ years. That is no small feat!"
#     fewshot_2_entities = "entities: NONE"
#     fewshot_2 = fewshot_2_message + "\n\n" + instruction + "\n\n" + fewshot_2_entities

#     target = "message: " + message + "\n\n" + instruction + "\n\n" + "entities:"

#     prompt = fewshot_1 + "\n\n--\n\n" + fewshot_2 + "\n\n--\n\n" + target

#     max_attempts = 3
#     count = 0
#     response = {}
#     entities_clean = ["NONE"]
#     while count < max_attempts:
#         try:
#             text = wrapped_chat_gpt_completion(
#                 messages=[
#                     {"role": "user", "content": prompt},
#                 ],
#                 temperature=0,
#                 max_tokens=max_tokens_length,
#             )

#             entities_clean = text.strip().replace("\n", "").split(" // ")
#             break
#         except:
#             count += 1

#     # OpenAI returns "NONE" if there are no entities
#     if len(entities_clean) == 1 and entities_clean[0] == "NONE":
#         return []

#     return entities_clean


# DEPRECATED [2024-03-26]: This NER function is deprecated and replaced by detect_hallucinations
# def get_named_entities_for_generated_message(message_id: int):
# """Get named entities for a generated message"""
# message: GeneratedMessage = GeneratedMessage.query.get(message_id)
# entities = get_named_entities(message.completion)

# return entities

# DEPRECATED [2024-03-26]: This NER function is deprecated and replaced by detect_hallucinations
# def run_check_message_has_bad_entities(message_id: int):
#     """Check if the message has any entities that are not in the prompt

#     If there are any entities that are not in the prompt, we flag the message and include the unknown entities.
#     """

#     message: GeneratedMessage = GeneratedMessage.query.get(message_id)
#     cta_id = message.message_cta
#     cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)

#     # entities = get_named_entities_for_generated_message(message_id=message_id)

#     prompt = message.prompt
#     sanitized_prompt = re.sub(
#         "[^0-9a-zA-Z]+",
#         " ",
#         prompt.lower(),
#     ).strip()

#     if cta is not None:
#         cta_text = cta.text_value
#     else:
#         cta_text = prompt
#     sanitized_cta_text = re.sub(
#         "[^0-9a-zA-Z]+",
#         " ",
#         cta_text.lower(),
#     ).strip()

#     flagged_entities = []
#     for entity in entities:
#         for exception in ner_exceptions:
#             if exception in entity:
#                 entity = entity.replace(exception, "").strip()

#         if entity.lower() in title_abbreviations:  # Abbreviated titles are OK
#             full_title = title_abbreviations[entity.lower()]
#             if full_title in prompt.lower():
#                 continue

#         sanitized_entity = re.sub(
#             "[^0-9a-zA-Z]+",
#             " ",
#             entity.lower(),
#         ).strip()

#         if (
#             sanitized_entity not in sanitized_prompt
#             and sanitized_entity not in sanitized_cta_text
#         ):
#             # HOTFIX: Dr.
#             if "dr." in sanitized_entity:
#                 continue
#             flagged_entities.append(entity)

#     generated_message: GeneratedMessage = GeneratedMessage.query.get(message_id)
#     generated_message.unknown_named_entities = flagged_entities
#     db.session.add(generated_message)
#     db.session.commit()

#     return len(flagged_entities) > 0, flagged_entities


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


def add_generated_msg_queue(
    client_sdr_id: int,
    li_message_urn_id: Union[str, None] = None,
    nylas_message_id: Union[str, None] = None,
    bump_framework_id: Optional[int] = None,
    bump_framework_title: Optional[str] = None,
    bump_framework_description: Optional[str] = None,
    bump_framework_length: Optional[str] = None,
    account_research_points: Optional[list] = None,
):
    """Adds a generated message to the queue

    Args:
        client_sdr_id (int): The ID of the client SDR
        li_message_urn_id (Union[str, None], optional): LinkedIn msg urn ID. Defaults to None.
        nylas_message_id (Union[str, None], optional): Nylas msg ID. Defaults to None.
        bump_framework_id (Optional[int], optional): Bump framework ID. Defaults to None.
        bump_framework_title (Optional[str], optional): Bump framework title. Defaults to None.
        bump_framework_description (Optional[str], optional): Bump framework description. Defaults to None.
        bump_framework_length (Optional[str], optional): Bump framework length. Defaults to None.
        account_research_points (Optional[str], optional): Account research points. Defaults to None.

    Returns:
        bool: True if added, False if not.
    """
    if not li_message_urn_id and not nylas_message_id:
        return False
    if li_message_urn_id and nylas_message_id:
        return False

    msg_queue = GeneratedMessageQueue.query.filter(
        GeneratedMessageQueue.client_sdr_id == client_sdr_id,
        GeneratedMessageQueue.li_message_urn_id == li_message_urn_id,
        GeneratedMessageQueue.nylas_message_id == nylas_message_id,
        GeneratedMessageQueue.bump_framework_id == bump_framework_id,
        GeneratedMessageQueue.bump_framework_title == bump_framework_title,
        GeneratedMessageQueue.bump_framework_description == bump_framework_description,
        GeneratedMessageQueue.bump_framework_length == bump_framework_length,
        GeneratedMessageQueue.account_research_points == account_research_points,
    ).first()
    if msg_queue:
        return False

    msg_queue = GeneratedMessageQueue(
        client_sdr_id=client_sdr_id,
        nylas_message_id=nylas_message_id,
        li_message_urn_id=li_message_urn_id,
        bump_framework_id=bump_framework_id,
        bump_framework_title=bump_framework_title,
        bump_framework_description=bump_framework_description,
        bump_framework_length=bump_framework_length,
        account_research_points=account_research_points,
    )
    db.session.add(msg_queue)
    db.session.commit()

    return True


def process_generated_msg_queue(
    client_sdr_id: int,
    li_message_urn_id: Union[str, None] = None,
    nylas_message_id: Union[str, None] = None,
    li_convo_entry_id: Optional[int] = None,
    email_convo_entry_id: Optional[int] = None,
):
    """Sets a li or email message to AI generated or not, then removes itself from the queue

    Args:
        client_sdr_id (int): The ID of the client SDR
        li_message_urn_id (Union[str, None], optional): LinkedIn msg urn ID. Defaults to None.
        nylas_message_id (Union[str, None], optional): Nylas msg ID. Defaults to None.
        convo_entry_id (int): The ID of the convo entry
        email_convo_entry_id (int): The ID of the email convo entry

    Returns:
        bool: True if removed, False if not.
    """

    if not li_message_urn_id and not nylas_message_id:
        return False
    if li_message_urn_id and nylas_message_id:
        return False

    msg_queue: GeneratedMessageQueue = GeneratedMessageQueue.query.filter(
        GeneratedMessageQueue.client_sdr_id == client_sdr_id,
        GeneratedMessageQueue.li_message_urn_id == li_message_urn_id,
        GeneratedMessageQueue.nylas_message_id == nylas_message_id,
    ).first()
    if not msg_queue:
        send_slack = False
        response_type = ""
        message = ""
        message_date = ""

        # Set the message to AI generated false
        if li_convo_entry_id:
            li_convo_entry: LinkedinConversationEntry = (
                LinkedinConversationEntry.query.get(li_convo_entry_id)
            )
            li_convo_entry.ai_generated = False
            db.session.commit()

            # Make sure that the message is at most 3 days old
            if datetime.utcnow() - li_convo_entry.date > timedelta(days=3):
                return False

            # Make sure that this is a SDR message
            if li_convo_entry.connection_degree != "You":
                return False

            # Get prospect information
            p: Prospect = Prospect.query.filter(
                Prospect.li_conversation_urn_id == li_convo_entry.thread_urn_id
            ).first()
            send_slack = True
            response_type = "LinkedIn"
            message = li_convo_entry.message
            message_date = str(li_convo_entry.date)

        elif email_convo_entry_id:
            email_convo_entry: EmailConversationMessage = (
                EmailConversationMessage.query.get(email_convo_entry_id)
            )
            email_convo_entry.ai_generated = False
            db.session.commit()

            # Make sure that the message is at most 3 days old
            if datetime.utcnow() - email_convo_entry.date_received > timedelta(days=3):
                return False

            # Make sure that this is a SDR message
            if not email_convo_entry.from_sdr:
                return False

            p: Prospect = Prospect.query.get(email_convo_entry.prospect_id)
            send_slack = True
            response_type = "Email"
            message = email_convo_entry.body
            message_date = str(email_convo_entry.date_received)

        # Send a slack message that this is Human generated
        if send_slack:
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            prospect_name = p.full_name if p else "Unknown Prospect"
            prospect_id = p.id if p else ""
            archetype: ClientArchetype = (
                ClientArchetype.query.get(p.archetype_id) if p else None
            )
            archetype_name = archetype.archetype if archetype else "Unknown Archetype"
            archetype_id = archetype.id if archetype else "Unknown Archetype"
            direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                auth_token=sdr.auth_token,
                prospect_id=prospect_id if prospect_id else "",
            )
            date_scraped = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            send_slack_message(
                message="🧑 New response from Human!",
                webhook_urls=[URL_MAP["csm-human-response"]],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🧑 Human Response - {sdr.name} [{response_type}]",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "_A human has manually responded to the convo below. Please make a bump framework if relevant to answer this for humans in the future._",
                            }
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Prospect:* <{direct_link}|{prospect_name} (#{prospect_id})>\n*Archetype:* {archetype_name}\n*Message Date:* {message_date}\n*Date Scraped:* {date_scraped}",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Custom Message:*\n```{message}```",
                        },
                    },
                ],
            )

        return False

    if li_message_urn_id:
        li_convo_msg: LinkedinConversationEntry = (
            LinkedinConversationEntry.query.filter(
                LinkedinConversationEntry.urn_id == li_message_urn_id,
                LinkedinConversationEntry.connection_degree == "You",
            ).first()
        )
        if not li_convo_msg:
            return False

        prospect: Prospect = Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.li_conversation_urn_id == li_convo_msg.thread_urn_id,
        ).first()
        prospect_name = prospect.full_name

        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        li_convo_msg.ai_generated = True
        li_convo_msg.bump_framework_id = msg_queue.bump_framework_id
        li_convo_msg.bump_framework_title = msg_queue.bump_framework_title
        li_convo_msg.bump_framework_description = msg_queue.bump_framework_description
        li_convo_msg.bump_framework_length = msg_queue.bump_framework_length
        li_convo_msg.account_research_points = msg_queue.account_research_points

        if msg_queue.bump_framework_id:
            bf: BumpFramework = BumpFramework.query.get(msg_queue.bump_framework_id)
            if bf:
                bf.etl_num_times_used = bf.etl_num_times_used or 0
                bf.etl_num_times_used += 1

        db.session.add(li_convo_msg)
        db.session.commit()

    if nylas_message_id:
        nylas_msg: EmailConversationMessage = EmailConversationMessage.query.filter(
            EmailConversationMessage.nylas_message_id == nylas_message_id,
            EmailConversationMessage.from_sdr == True,
        ).first()
        if not nylas_msg:
            return False
        nylas_msg.ai_generated = True if msg_queue else False
        db.session.add(nylas_msg)
        db.session.commit()

    if not msg_queue:
        return False

    db.session.delete(msg_queue)
    db.session.commit()

    print("Processed generated message queue")

    return True


def send_sent_by_sellscale_notification(
    prospect_id: int, message: str, bump_framework_id: Optional[int] = None
):
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_name = prospect.full_name
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    bump_framework_name = "Smart Generate"
    if bump_framework_id:
        bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
        if bump_framework:
            bump_framework_name = "'" + bump_framework.title + "'"

    direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
        auth_token=client_sdr.auth_token,
        prospect_id=prospect_id if prospect_id else "",
    )

    if (
        prospect.overall_status
        in (
            ProspectOverallStatus.ACTIVE_CONVO,
            ProspectOverallStatus.DEMO,
        )
        and prospect.li_last_message_from_prospect
    ):
        status: str = prospect.status.value if prospect.status else "UNKNOWN"
        status = status.split("_")
        status = " ".join(word.capitalize() for word in status)

        success = create_and_send_slack_notification_class_message(
            notification_type=SlackNotificationType.LINKEDIN_AI_REPLY,
            arguments={
                "client_sdr_id": client_sdr.id,
                "prospect_id": prospect_id,
                "bump_framework_id": bump_framework_id,
                "status": status,
                "ai_response": message,
            },
        )

        # send_slack_message(
        #     message="SellScale AI just replied to prospect!",
        #     webhook_urls=[
        #         URL_MAP["eng-sandbox"],
        #         client.pipeline_notifications_webhook_url,
        #     ],
        #     blocks=[
        #         {
        #             "type": "header",
        #             "text": {
        #                 "type": "plain_text",
        #                 "text": "💬 SellScale AI just replied to " + prospect_name,
        #                 "emoji": True,
        #             },
        #         },
        #         {
        #             "type": "section",
        #             "text": {
        #                 "type": "mrkdwn",
        #                 "text": f"Convo Status: `{status}`",
        #             },
        #         },
        #         {
        #             "type": "section",
        #             "text": {
        #                 "type": "mrkdwn",
        #                 "text": "*✨ AI Reply Framework:* `{bump_framework_name}`".format(
        #                     bump_framework_name=bump_framework_name
        #                     if bump_framework_name
        #                     else "-"
        #                 ),
        #             },
        #         },
        #         {
        #             "type": "section",
        #             "text": {
        #                 "type": "mrkdwn",
        #                 "text": '*{prospect_first_name}*:\n>"{prospect_message}"\n\n*{first_name} (AI)*:\n>"{ai_response}"'.format(
        #                     prospect_first_name=prospect.first_name,
        #                     prospect_name=prospect_name,
        #                     prospect_message=prospect.li_last_message_from_prospect.replace(
        #                         "\n", " "
        #                     )
        #                     if prospect.li_last_message_from_prospect
        #                     else "-",
        #                     ai_response=message.replace("\n", " "),
        #                     first_name=client_sdr.name.split(" ")[0],
        #                 ),
        #             },
        #         },
        #         {"type": "divider"},
        #         {
        #             "type": "context",
        #             "elements": [
        #                 {
        #                     "type": "plain_text",
        #                     "text": "🧳 Title: "
        #                     + str(prospect.title)
        #                     + " @ "
        #                     + str(prospect.company)[0:20]
        #                     + ("..." if len(prospect.company) > 20 else ""),
        #                     "emoji": True,
        #                 },
        #                 {
        #                     "type": "plain_text",
        #                     "text": "🪜 Status: "
        #                     + prospect.status.value.replace("_", " ").lower(),
        #                     "emoji": True,
        #                 },
        #                 {
        #                     "type": "plain_text",
        #                     "text": "📌 SDR: " + client_sdr.name,
        #                     "emoji": True,
        #                 },
        #             ],
        #         },
        #         {
        #             "type": "section",
        #             "block_id": "sectionBlockWithLinkButton",
        #             "text": {"type": "mrkdwn", "text": "View Conversation in Sight"},
        #             "accessory": {
        #                 "type": "button",
        #                 "text": {
        #                     "type": "plain_text",
        #                     "text": "View Convo",
        #                     "emoji": True,
        #                 },
        #                 "value": direct_link,
        #                 "url": direct_link,
        #                 "action_id": "button-action",
        #             },
        #         },
        #     ],
        # )

    return True


@celery.task
def generate_message_bumps():
    # For each prospect that's in one of the states (and client sdr has auto_generate_messages enabled)
    sdrs: List[ClientSDR] = (
        ClientSDR.query.join(Client)
        .filter(
            ClientSDR.active == True,
            Client.active == True,
            ClientSDR.auto_generate_messages == True,
            ClientSDR.li_at_token != "INVALID",
        )
        .order_by(func.random())
        .all()
    )

    for sdr in sdrs:
        prospects: List[Prospect] = Prospect.query.filter(
            Prospect.client_sdr_id == sdr.id,
            Prospect.status.in_(
                [
                    "ACCEPTED",
                    "RESPONDED",
                    "ACTIVE_CONVO",
                    "ACTIVE_CONVO_QUESTION",
                    "ACTIVE_CONVO_QUAL_NEEDED",
                    "ACTIVE_CONVO_OBJECTION",
                    "ACTIVE_CONVO_SCHEDULING",
                    "ACTIVE_CONVO_NEXT_STEPS",
                    "ACTIVE_CONVO_REVIVAL",
                ]
            ),
            or_(
                Prospect.hidden_until == None,
                Prospect.hidden_until <= datetime.utcnow(),
            ),
            Prospect.active == True,
        ).all()

        # print(f"Generating bumps for {len(prospects)} prospects...")

        for prospect in prospects:
            # Get the archetype
            archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )

            # If the archetype is unassigned contact, then we don't generate a bump
            if archetype.is_unassigned_contact_archetype:
                continue

            # CHECK: If the prospect is in ACCEPTED stage and the message delay on the archetype is not quite up
            #      then we don't generate a bump
            if prospect.status == ProspectStatus.ACCEPTED:
                # If the archetype has a message delay, check if it's been long enough by referencing status records
                if archetype and archetype.first_message_delay_days:
                    # Get the first status record
                    status_record: ProspectStatusRecords = (
                        ProspectStatusRecords.query.filter(
                            ProspectStatusRecords.prospect_id == prospect.id,
                            ProspectStatusRecords.to_status == ProspectStatus.ACCEPTED,
                        )
                        .order_by(ProspectStatusRecords.created_at.asc())
                        .first()
                    )
                    if status_record:
                        # If the first status record is less than the delay, then we don't generate a bump
                        if (
                            datetime.utcnow() - status_record.created_at
                        ).days < archetype.first_message_delay_days:
                            continue

            # Generate the bump
            success = generate_prospect_bump(
                client_sdr_id=prospect.client_sdr_id,
                prospect_id=prospect.id,
            )

            # IMPORTANT: this short circuits this loop if we successfully generate a bump
            #       that way it only generates a bump once every 2 minutes
            if success == True:
                return


def clear_auto_generated_bumps(bump_framework_id: int) -> bool:
    """Clears all generated_message_auto_bump entries that have the given bump_framework_id

    Is used for outdated bump frameworks

    Args:
        bump_framework_id (int): Bump Framework ID

    Returns:
        bool: True if successful
    """

    generated_bumps: List[
        GeneratedMessageAutoBump
    ] = GeneratedMessageAutoBump.query.filter(
        GeneratedMessageAutoBump.bump_framework_id == bump_framework_id
    ).all()

    for bump in generated_bumps:
        db.session.delete(bump)
    db.session.commit()

    return True


@celery.task
def generate_prospect_bump_task(client_sdr_id: int, prospect_id: int):
    generate_prospect_bump(client_sdr_id=client_sdr_id, prospect_id=prospect_id)


def generate_prospect_bumps_from_id_list(client_sdr_id: int, prospect_ids: list):
    bumps: list[GeneratedMessageAutoBump] = GeneratedMessageAutoBump.query.filter(
        GeneratedMessageAutoBump.client_sdr_id == client_sdr_id,
        GeneratedMessageAutoBump.prospect_id.in_(prospect_ids),
    ).all()
    for bump in bumps:
        db.session.delete(bump)
        db.session.commit()

    for delay, prospect_id in enumerate(prospect_ids):
        generate_prospect_bump_task.apply_async(
            args=(client_sdr_id, prospect_id), countdown=delay * 3
        )
        # generate_prospect_bump_task(client_sdr_id, prospect_id)


def generate_prospect_bump(client_sdr_id: int, prospect_id: int):
    """Generates a follow up message for a prospect, using their convo history and bump frameworks

    Args:
        client_sdr_id (int): Client SDR ID
        prospect_id (int): Prospect ID
    """

    try:
        from src.voyager.linkedin import LinkedIn
        from src.voyager.services import fetch_conversation

        api = LinkedIn(client_sdr_id)
        _, _ = fetch_conversation(api, prospect_id, True)

        latest_convo_entries = get_li_convo_history(prospect_id)
        if len(latest_convo_entries) == 0:
            return False

        # Check if we've already generated a bump for this convo
        prev_bump_msg: GeneratedMessageAutoBump = (
            GeneratedMessageAutoBump.query.filter(
                GeneratedMessageAutoBump.prospect_id == prospect_id,
            )
            .order_by(GeneratedMessageAutoBump.created_at.desc())
            .first()
        )

        if prev_bump_msg:
            if prev_bump_msg.latest_li_message_id == latest_convo_entries[-1].li_id:
                # Already generated a bump for this message
                return False

        # Create a new bump message first, then update later
        dupe_bump_msg: GeneratedMessageAutoBump = GeneratedMessageAutoBump.query.filter(
            GeneratedMessageAutoBump.latest_li_message_id
            == latest_convo_entries[-1].li_id,
        ).first()
        if dupe_bump_msg:
            # Already generated a bump for this message
            return False

        # If we've already hit our max bump count, skip
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_archetype: ClientArchetype = ClientArchetype.query.get(
            prospect.archetype_id
        )
        if (
            prospect.times_bumped
            and client_archetype.li_bump_amount <= prospect.times_bumped
        ):
            return False

        bump_msg = GeneratedMessageAutoBump(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            latest_li_message_id=latest_convo_entries[-1].li_id,
            message=".",
            bump_framework_id=None,
            bump_framework_title=None,
            bump_framework_description=None,
            bump_framework_length=None,
            account_research_points=None,
            send_status=SendStatus.IN_QUEUE,
        )
        db.session.add(bump_msg)
        db.session.commit()

        ### Starting message generation... ###

        prospect: Prospect = Prospect.query.get(prospect_id)
        data = generate_followup_response(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            overall_status=prospect.overall_status,
            li_status=prospect.status,
            bump_count=prospect.times_bumped,
            convo_history=latest_convo_entries,
            # show_slack_messages=False,
        )
        if not data:
            return False

        ### Message generation complete ###

        send_slack_message(
            message=f" - Made response, finalizing bump message...",
            webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
        )

        # Update bump message
        bump_msg: GeneratedMessageAutoBump = GeneratedMessageAutoBump.query.filter(
            GeneratedMessageAutoBump.latest_li_message_id
            == latest_convo_entries[-1].li_id,
        ).first()
        if not bump_msg:
            raise Exception(
                f"Could not find bump message with li_message_id {latest_convo_entries[-1].li_id}"
            )

        bump_msg.message = data.get("response")
        bump_msg.bump_framework_id = data.get("bump_framework_id")
        bump_msg.bump_framework_title = data.get("bump_framework_title")
        bump_msg.bump_framework_description = data.get("bump_framework_description")
        bump_msg.bump_framework_length = data.get("bump_framework_length")
        bump_msg.account_research_points = data.get("account_research_points")

        db.session.add(bump_msg)
        db.session.commit()

        send_slack_message(
            message=f" - Complete!",
            webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
        )

        send_slack_message(
            message=f"- Complete! _Generated a bump for {prospect.full_name} ({prospect.id})_",
            webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
        )
        send_slack_message(
            message=f"*Bump Message:* '{bump_msg.message}'",
            webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
        )

        return True

    except Exception as e:
        send_slack_message(
            message=f"🛑 *Error occurred, broken generation:* '{e}'" "",
            webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
        )

        db.session.rollback()
        return False


def generate_followup_response(
    client_sdr_id: int,
    prospect_id: int,
    overall_status: ProspectOverallStatus,
    li_status: ProspectStatus,
    bump_count: int,
    convo_history: List[LinkedInConvoMessage],
    show_slack_messages: bool = True,
    bump_framework_template_id: Optional[BumpFrameworkTemplates] = None,
):
    try:
        # Get bump frameworks
        prospect: Prospect = Prospect.query.get(prospect_id)

        from src.bump_framework.services import get_bump_frameworks_for_sdr

        # if status in ACCEPTED or BUMPED, archetype ids is a valdi list
        # else archetype ids is None
        archetype_ids = (
            [prospect.archetype_id]
            if overall_status
            in [ProspectOverallStatus.ACCEPTED, ProspectOverallStatus.BUMPED]
            else []
        )
        include_archetype_sequence_id = (
            prospect.archetype_id
            if prospect.status == ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE
            else None
        )

        bump_frameworks: list[dict] = get_bump_frameworks_for_sdr(
            client_sdr_id=client_sdr_id,
            overall_statuses=[overall_status],
            # substatuses=[li_status.value] if "ACTIVE_CONVO_" in li_status.value else [],
            client_archetype_ids=archetype_ids,
            active_only=True,
            bumped_count=bump_count,
            default_only=False,
            include_archetype_sequence_id=include_archetype_sequence_id,
        )

        # Filter by active convo substatus
        if overall_status.value == "ACTIVE_CONVO":
            # Different behavior for Continue the Sequence
            if prospect.status == ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE:
                num_messages_from_sdr = len(
                    [x for x in convo_history if x.connection_degree == "You"]
                )

                bump_frameworks = [
                    x
                    for x in bump_frameworks
                    if x.get("overall_status") == "BUMPED"
                    and x.get("bumped_count") == num_messages_from_sdr
                ]
            else:
                bump_frameworks = [
                    x for x in bump_frameworks if x.get("substatus") == li_status.value
                ]

        # Filter by bumped count
        if overall_status.value == "BUMPED":
            bump_frameworks = [
                x for x in bump_frameworks if x.get("bumped_count") == bump_count
            ]

        ### Starting message generation... ###

        if show_slack_messages:
            send_slack_message(
                message=f"*Generating a bump for SDR #{client_sdr_id} and prospect #{prospect_id}...*",
                webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
            )

        if len(bump_frameworks) > 0:
            # Determine the best bump framework
            if len(bump_frameworks) == 1:
                framework_id = bump_frameworks[0].get("id")
            else:
                if overall_status in [
                    ProspectOverallStatus.ACCEPTED,
                    ProspectOverallStatus.BUMPED,
                ]:
                    framework_id = random.choice(bump_frameworks).get("id", -1)
                else:
                    framework_id = determine_best_bump_framework_from_convo(
                        convo_history=convo_history,
                        bump_framework_ids=[bf.get("id", -1) for bf in bump_frameworks],
                    )

            if show_slack_messages:
                send_slack_message(
                    message=f" - Found best framework: {framework_id}",
                    webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
                )

            best_framework = next(
                (bf for bf in bump_frameworks if bf.get("id") == framework_id),
                None,
            )

            if show_slack_messages:
                send_slack_message(
                    message=f" - Selected Framework: {best_framework.get('title')} (#{best_framework.get('id')})",
                    webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
                )
        else:
            best_framework = None

        # Determine the best account research
        points = ResearchPoints.get_research_points_by_prospect_id(
            prospect_id,
            bump_framework_id=best_framework.get("id") if best_framework else None,
        )
        random_sample_points = random.sample(points, min(len(points), 3))

        if show_slack_messages:
            send_slack_message(
                message=f" - Account Research (selected {len(random_sample_points)}/{len(points)} points)",
                webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
            )

        account_research_points = []
        research_str = ""

        # Only include account research points if bump framework allows it
        use_account_research = (
            best_framework.get("use_account_research") if best_framework else True
        )
        if use_account_research:
            for point in random_sample_points:
                account_research_points.append(
                    point.value,
                )
                research_str += f"{point.value}\n"

        # Generate response
        from src.li_conversation.services import (
            generate_chat_gpt_response_to_conversation_thread,
        )

        response, prompt = generate_chat_gpt_response_to_conversation_thread(
            prospect_id=prospect_id,
            convo_history=convo_history,
            bump_framework_id=best_framework.get("id") if best_framework else None,
            account_research_copy=research_str,
            bump_framework_template_id=bump_framework_template_id,
        )  # type: ignore

        if show_slack_messages:
            send_slack_message(
                message=f" - Generated message!",
                webhook_urls=[URL_MAP["operations-auto-bump-msg-gen"]],
            )

        return {
            "response": response,
            "prompt": prompt,
            "bump_framework_id": best_framework.get("id") if best_framework else None,
            "bump_framework_title": (
                best_framework.get("title") if best_framework else None
            ),
            "bump_framework_description": (
                best_framework.get("description") if best_framework else None
            ),
            "bump_framework_length": (
                best_framework.get("bump_length") if best_framework else None
            ),
            "bump_framework_delay": (
                best_framework.get("bump_delay_days") if best_framework else None
            ),
            "account_research_points": account_research_points,
        }

    except Exception as e:
        raise e


def get_li_convo_history(prospect_id: int) -> List[LinkedInConvoMessage]:
    """
    Fetches the last 5 messages of a prospect's LinkedIn conversation
    """

    prospect: Prospect = Prospect.query.get(prospect_id)

    # Fetch the last 5 messages of their convo
    latest_convo_entries: List[LinkedinConversationEntry] = (
        LinkedinConversationEntry.query.filter_by(
            conversation_url=f"https://www.linkedin.com/messaging/thread/{prospect.li_conversation_urn_id}/"
        )
        .order_by(LinkedinConversationEntry.date.desc())
        .limit(10)
        .all()
    )

    # sort in reverse order of date
    latest_convo_entries.sort(key=lambda x: x.date)

    return [
        LinkedInConvoMessage(
            message=convo_entry.message,
            connection_degree=convo_entry.connection_degree,
            author=convo_entry.author,
            li_id=convo_entry.id,
            date=convo_entry.date,
        )
        for convo_entry in latest_convo_entries
    ]


def get_li_convo_history_transcript_form(prospect_id: int) -> str:
    """Gets the transcript of a prospect's LinkedIn conversation

    Args:
        prospect_id (int): Prospect ID

    Returns:
        str: Transcript of the conversation
    """
    convo_history = get_li_convo_history(
        prospect_id=prospect_id,
    )

    msg = next(filter(lambda x: x.connection_degree == "You", convo_history), None)
    if not msg:
        raise Exception("No message from SDR found in convo_history")

    transcript = "\n\n".join(
        [x.author + " (" + str(x.date)[0:10] + "): " + x.message for x in convo_history]
    )

    return transcript


def get_prospect_bump(client_sdr_id: int, prospect_id: int):
    bump_msg: GeneratedMessageAutoBump = (
        GeneratedMessageAutoBump.query.filter(
            GeneratedMessageAutoBump.client_sdr_id == client_sdr_id,
            GeneratedMessageAutoBump.prospect_id == prospect_id,
        )
        .order_by(GeneratedMessageAutoBump.created_at.desc())
        .first()
    )
    if not bump_msg:
        return None

    return bump_msg


def delete_prospect_bump(client_sdr_id: int, prospect_id: int):
    bump_msgs: List[GeneratedMessageAutoBump] = GeneratedMessageAutoBump.query.filter(
        GeneratedMessageAutoBump.client_sdr_id == client_sdr_id,
        GeneratedMessageAutoBump.prospect_id == prospect_id,
    ).all()
    if not bump_msgs:
        return False

    for bump_msg in bump_msgs:
        db.session.delete(bump_msg)
    db.session.commit()

    return True


def update_stack_ranked_configuration_data(
    configuration_id: int,
    instruction: Optional[str],
    completion_1: Optional[str],
    completion_2: Optional[str],
    completion_3: Optional[str],
    completion_4: Optional[str],
    completion_5: Optional[str],
    completion_6: Optional[str],
    completion_7: Optional[str],
):
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.get(configuration_id)
    )

    if not srmgc:
        return False

    if instruction:
        srmgc.instruction = instruction
    if completion_1:
        srmgc.completion_1 = completion_1
    if completion_2:
        srmgc.completion_2 = completion_2
    if completion_3:
        srmgc.completion_3 = completion_3
    if completion_4:
        srmgc.completion_4 = completion_4
    if completion_5:
        srmgc.completion_5 = completion_5
    if completion_6:
        srmgc.completion_6 = completion_6
    if completion_7:
        srmgc.completion_7 = completion_7

    new_computed_prompt = srmgc.instruction + "\n------\n"
    if srmgc.prompt_1 and srmgc.completion_1:
        new_computed_prompt += (
            "prompt: "
            + srmgc.prompt_1
            + "\ncompletion: "
            + srmgc.completion_1
            + "\n------\n"
        )
    if srmgc.prompt_2 and srmgc.completion_2:
        new_computed_prompt += (
            "prompt: "
            + srmgc.prompt_2
            + "\ncompletion: "
            + srmgc.completion_2
            + "\n------\n"
        )
    if srmgc.prompt_3 and srmgc.completion_3:
        new_computed_prompt += (
            "prompt: "
            + srmgc.prompt_3
            + "\ncompletion: "
            + srmgc.completion_3
            + "\n------\n"
        )
    if srmgc.prompt_4 and srmgc.completion_4:
        new_computed_prompt += (
            "prompt: "
            + srmgc.prompt_4
            + "\ncompletion: "
            + srmgc.completion_4
            + "\n------\n"
        )
    if srmgc.prompt_5 and srmgc.completion_5:
        new_computed_prompt += (
            "prompt: "
            + srmgc.prompt_5
            + "\ncompletion: "
            + srmgc.completion_5
            + "\n------\n"
        )
    if srmgc.prompt_6 and srmgc.completion_6:
        new_computed_prompt += (
            "prompt: "
            + srmgc.prompt_6
            + "\ncompletion: "
            + srmgc.completion_6
            + "\n------\n"
        )
    if srmgc.prompt_7 and srmgc.completion_7:
        new_computed_prompt += (
            "prompt: "
            + srmgc.prompt_7
            + "\ncompletion: "
            + srmgc.completion_7
            + "\n------\n"
        )
    new_computed_prompt += "prompt: {prompt}\ncompletion:"
    srmgc.computed_prompt = new_computed_prompt

    db.session.add(srmgc)
    db.session.commit()

    return True


def refresh_computed_prompt_for_stack_ranked_configuration(configuration_id: int):
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.get(configuration_id)
    )

    if not srmgc:
        return False

    new_computed_prompt = srmgc.instruction + "\n------\n"
    for i in range(1, 8):
        prompt_attr_key = "prompt_" + str(i)
        completion_attr_key = "completion_" + str(i)

        prompt = getattr(srmgc, prompt_attr_key)
        completion = getattr(srmgc, completion_attr_key)

        if prompt and completion:
            new_computed_prompt += (
                "prompt: " + prompt + "\ncompletion: " + completion + "\n------\n"
            )

    new_computed_prompt += "prompt: {prompt}\ncompletion:"
    srmgc.computed_prompt = new_computed_prompt

    db.session.add(srmgc)
    db.session.commit()

    return True


def generate_li_convo_init_msg(prospect_id: int, template_id: Optional[int] = None):
    """Generates the initial message for a linkedin conversation

    Args:
        prospect_id (int): The prospect id

    Returns:
        str: The message
        dict: The generation metadata
    """

    from src.ml.fine_tuned_models import get_config_completion
    from src.message_generation.services import generate_prompt
    from src.client.models import ClientSDR
    from src.message_generation.services import get_notes_and_points_from_perm
    from src.message_generation.models import GeneratedMessageType
    from src.message_generation.services_stack_ranked_configurations import (
        get_top_stack_ranked_config_ordering,
        random_cta_for_prospect,
    )
    from src.message_generation.models import StackRankedMessageGenerationConfiguration
    from src.message_generation.services import (
        generate_batch_of_research_points_from_config,
    )
    from src.li_conversation.services import ai_initial_li_msg_prompt

    ### Use new template-based generation ###
    prospect: Prospect = Prospect.query.get(prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    if archetype.template_mode:
        if not template_id:
            template: LinkedinInitialMessageTemplate = (
                LinkedinInitialMessageTemplate.get_random(prospect.archetype_id)
            )
        else:
            template: LinkedinInitialMessageTemplate = (
                LinkedinInitialMessageTemplate.query.get(template_id)
            )

        prompt = ai_initial_li_msg_prompt(
            client_sdr_id=prospect.client_sdr_id,
            prospect_id=prospect_id,
            template=template.message,
            additional_instructions=template.additional_instructions or "",
            research_points=template.research_points or [],
        )

        completion = get_text_generation(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            model="gpt-4",
            type="LI_MSG_INIT",
            prospect_id=prospect_id,
            client_sdr_id=prospect.client_sdr_id,
            use_cache=False,
        )

        print("completion", completion)

        return completion, {
            "prompt": prompt,
            "cta": None,
            "research_points": None,
            "notes": None,
        }

    ### Use legacy CTA + Voice generation ###
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
        get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

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
    perm = perms[0]

    cta, cta_id = random_cta_for_prospect(prospect_id=prospect_id)
    notes, research_points, _ = get_notes_and_points_from_perm(perm, cta_id=cta_id)
    prompt, _ = generate_prompt(prospect_id=prospect_id, notes=notes)

    if len(research_points) == 0:
        return None, None

    raw_research_points = ResearchPoints.query.filter(
        ResearchPoints.id.in_(research_points)
    ).all()
    rp_values = [x.value for x in raw_research_points] if raw_research_points else []

    completion, few_shot_prompt = get_config_completion(TOP_CONFIGURATION, prompt)

    return completion, {
        "prompt": few_shot_prompt,
        "cta": cta,
        "research_points": research_points,
        "notes": rp_values,
    }


@celery.task(bind=True, max_retries=3)
def scribe_sample_email_generation(
    self, USER_LINKEDIN: str, USER_EMAIL: str, PROSPECT_LINKEDIN: str, BLOCK_KEY: str
):
    random_code = generate_random_alphanumeric(num_chars=10)

    BLOCK_OPTIONS = {
        "email": """1. Come up with a fun subject line using the company or prospect name
2. Include a greeting with Hi, Hello, or Hey with their first name
3. Personalized 1-2 lines. Mentioned details about them, their role, their company, or other relevant pieces of information. Use personal details about them to be natural and personal.
4. Inferring what they do from their title, transition into introducing our service
5. Mention what we do and offer and how it can help them based on their background, company, and key details.
5. Use the objective for a call to action
6. End with Best, (new line) (My Name) (new line) (Title)
7. Have a P.S with a short, personalized line. Ideally it is something that is relevant to their background or interests""",
        "resurrection": """0. Come up with a zesty, fun subject line that is personalized to them
1. Start by saying we haven't heard from them, but make it lighthearted and include a joke, perhaps related to their industry or role
2. Personalize title: Include the prospect's name in the greeting.
3. Mention we've been trying to get ahold of them, and if what our company does is still a priority
4. Ask if they've given up
5. Closing: Sign off with "Best," (newline) Your Name.
Be casual and creative.""",
        "warm_intro": """1. Start with a greeting
2. Mention a unique fact or insight about their company
3. Transition into how we may be able to partner to help the company. Then explain what we do.
4. Ask if there's any interest to meet
Note: don't make it too salesly. Make it brief and casual.""",
        "linkedin": """1. Greeting: open with a friendly greeting
2. Specific detail about them: Include a personalized detail related to their background or role.
3. Write a short sentence on what we do and how it relates to them.
Call to action (CTA): Encourage them to connect or engage further.

Keep the whole message 1-2 sentences and 1 paragraph long. Keep it short!""",
    }

    key = BLOCK_KEY
    if key not in BLOCK_OPTIONS:
        key = "email"
    BLOCKS = BLOCK_OPTIONS[BLOCK_KEY]

    plg_lead = PLGProductLeads(
        email=USER_EMAIL,
        user_linkedin_url=USER_LINKEDIN,
        prospect_linkedin_url=PROSPECT_LINKEDIN,
        blocks=BLOCKS,
        is_test=False,
    )
    db.session.add(plg_lead)
    db.session.commit()

    try:
        CLIENT_ID = 38  # SellScale Scribe client
        CLIENT_ARCHETYPE_ID = 268  # SellScale Scribe archetype
        CLIENT_SDR_ID = 89  # SellScale Scribe SDR

        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] Started new email generation task",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )

        def get_indiduals_prospect_id_from_linkedin_url(input_linkedin_url):
            linkedin_slug = get_linkedin_slug_from_url(input_linkedin_url)
            prospect = (
                Prospect.query.filter(
                    Prospect.linkedin_url.ilike("%" + linkedin_slug + "%")
                )
                .filter(Prospect.client_id == CLIENT_ID)
                .first()
            )
            prospect_id = None
            if prospect:
                prospect_id = prospect.id
            else:
                success, prospect_id = create_prospect_from_linkedin_link(
                    archetype_id=CLIENT_ARCHETYPE_ID,
                    url=input_linkedin_url,
                    synchronous_research=True,
                    allow_duplicates=False,
                )
                prospect = Prospect.query.filter_by(id=prospect_id).first()
                prospect.linkedin_url = "linkedin.com/in/" + linkedin_slug
                db.session.add(prospect)
                db.session.commit()

            send_slack_message(
                message=f"[{USER_EMAIL} {random_code}] Generating research points for prospect ({prospect_id}) ({input_linkedin_url}) ...",
                webhook_urls=[URL_MAP["ops-scribe-submissions"]],
            )
            get_research_and_bullet_points_new(
                prospect_id=prospect_id,
                test_mode=False,
            )

            prospect = Prospect.query.filter_by(id=prospect_id).first()
            # research_points = ResearchPoints.get_research_points_by_prospect_id(
            #     prospect_id
            # )

            return prospect_id

        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] Finding prospect ({PROSPECT_LINKEDIN}) on LinkedIn ...",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )
        prospect = get_indiduals_prospect_id_from_linkedin_url(PROSPECT_LINKEDIN)
        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] Finding user ({USER_LINKEDIN}) on LinkedIn ...",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )
        user = get_indiduals_prospect_id_from_linkedin_url(USER_LINKEDIN)

        prospect_rp = ResearchPayload.query.filter_by(prospect_id=prospect).first()
        user_rp = ResearchPayload.query.filter_by(prospect_id=user).first()

        if prospect_rp:
            prospect_rp = prospect_rp.payload
        if user_rp:
            user_rp = user_rp.payload

        # names
        structure = BLOCKS
        sdr_name = (
            deep_get(user_rp, "personal.first_name", "")
            + " "
            + deep_get(user_rp, "personal.last_name", "")
        )
        sdr_title = deep_get(user_rp, "personal.sub_title", "")
        sdr_company_name = deep_get(
            user_rp, "personal.position_groups.0.company.name", ""
        )
        sdr_company_description = deep_get(user_rp, "company.details.description") or ""
        sdr_company_tagline = deep_get(user_rp, "company.details.tagline") or ""
        prospect_name = (
            deep_get(prospect_rp, "personal.first_name", "")
            + " "
            + deep_get(prospect_rp, "personal.last_name", "")
        )
        prospect_title = deep_get(prospect_rp, "personal.sub_title")
        prospect_bio = deep_get(prospect_rp, "personal.summary") or ""
        prospect_company_name = deep_get(
            prospect_rp, "personal.position_groups.0.company.name"
        )
        prospect_research_points = ResearchPoints.get_research_points_by_prospect_id(
            prospect
        )
        prospect_research_joined = "\n".join(
            ["- " + rp.value for rp in prospect_research_points]
        )

        prompt = """You are a sales development representative writing on behalf of the SDR.

        Write a personalized cold email short enough I could read on an iphone easily. Here's the structure
        {structure}

        Note - you do not need to include all info.

        SDR info:
        SDR Name: {client_sdr_name}
        Title: {client_sdr_title}

        Company info:
        Tagline: {company_tagline}
        Company description: {company_description}

        Prospect info:
        Prospect Name: {prospect_name}
        Prospect Title: {prospect_title}
        Prospect Bio:
        "{prospect_bio}"
        Prospect Company Name: {prospect_company_name}

        More research:
        {prospect_research}

        Final instructions
        - Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed".
        - Use markdown as needed to accomplish the instructions.

        Generate the subject line, one line break, then the email body. Do not include the word 'Subject:' or 'Email:' in the output.

        I want to write this email with the following objective: {persona_contact_objective}

        Output:""".format(
            structure=structure,
            client_sdr_name=sdr_name,
            client_sdr_title=sdr_title,
            company_tagline=sdr_company_tagline,
            company_description=sdr_company_description,
            prospect_name=prospect_name,
            prospect_title=prospect_title,
            prospect_bio=prospect_bio,
            prospect_company_name=prospect_company_name,
            prospect_research=prospect_research_joined,
            persona_contact_objective="Get on an intro call",
        )

        print(prompt)

        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] Generating a new completion ...",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )
        completion = wrapped_chat_gpt_completion(
            [
                {"role": "system", "content": prompt},
            ],
            temperature=0.65,
            max_tokens=240,
            model=OPENAI_CHAT_GPT_4_MODEL,
        )
        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] Generated completion ...",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )

        # make call to zapier webhook with completion in payload
        zapier_webhook_url = "https://hooks.zapier.com/hooks/catch/13803519/318v030/"
        zapier_payload = {
            "user_first_name": deep_get(user_rp, "personal.first_name", ""),
            "user_company_title_case": deep_get(
                user_rp, "personal.position_groups.0.company.name", ""
            ),
            "email": USER_EMAIL,
            "completion": completion,
        }
        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] Sending email to user via a Zap...",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )
        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] Generated Email:\n{completion}",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )
        r = requests.post(zapier_webhook_url, json=zapier_payload)
    except Exception as e:
        # Mark launch as failed
        print("Error occurred: " + str(e))
        send_slack_message(
            message=f"[{USER_EMAIL} {random_code}] 🚨🚨 Error occurred: {str(e)}",
            webhook_urls=[URL_MAP["ops-scribe-submissions"]],
        )

        # Retry
        self.retry(exc=e, countdown=5)


def get_cta_types():
    return [
        "In-Person-based",
        "Help-Based",
        "Feedback-Based",
        "Problem-Based",
        "Priority-Based",
        "Persona-Based",
        "Solution-Based",
        "Company-Based",
        "Time-Based",
        "Demo-Based",
        "Interest-Based",
        "Test-Based",
        "Question-Based",
        "Expertise-Based",
        "Meeting-Based",
        "Pain-Based",
        "FOMO-Based",
        "Competitor-Based",
        "Discovery-Based",
        "Intent-Based",
        "Result-Based",
        "Role-Based",
        "Resource-Based",
        "Connection-Based",
        "Event-Based",
    ]


def get_prospect_research_points(
    prospect_id: int, research_points: list[str]
) -> list[dict]:
    """
    Gets the research points for a prospect, filtered by the research points given
    """

    get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

    all_research_points: list[
        ResearchPoints
    ] = ResearchPoints.get_research_points_by_prospect_id(prospect_id)

    found_research_points = [
        research_point
        for research_point in all_research_points
        if research_point.research_point_type in research_points
    ]

    return [research_point.to_dict() for research_point in found_research_points]


def num_messages_in_linkedin_queue(client_sdr_id: int):
    query = """
        select count(distinct prospect.id)
        from generated_message
            join prospect on prospect.approved_outreach_message_id = generated_message.id
        where generated_message.message_status = 'QUEUED_FOR_OUTREACH'
            and prospect.status = 'QUEUED_FOR_OUTREACH'
            and prospect.client_sdr_id = :client_sdr_id
    """

    result = db.session.execute(query, {"client_sdr_id": client_sdr_id}).first()

    return result[0] if result else 0


def is_business_hour(dt):
    """Check if the datetime is within business hours (9 AM to 5 PM) on a weekday."""
    return dt.weekday() < 5 and 9 <= dt.hour < 17


def next_business_hour(dt):
    """Get the next business hour from the given datetime."""
    if dt.hour >= 17:  # After 5 PM
        dt = dt + timedelta(days=1)
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    elif dt.hour < 9:  # Before 9 AM
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    if dt.weekday() >= 5:  # Weekend
        dt += timedelta(days=7 - dt.weekday())
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    return dt


def schedule_cached_messages(client_sdr_id: int, prospect_ids: list[int]):
    from src.automation.orchestrator import add_process_for_future

    generated_message_autobumps = GeneratedMessageAutoBump.query.filter(
        GeneratedMessageAutoBump.client_sdr_id == client_sdr_id,
        GeneratedMessageAutoBump.prospect_id.in_(prospect_ids),
    )

    sent_prospect_ids = set()

    scheduled_send_date = datetime.now() + timedelta(minutes=15)
    scheduled_send_date = next_business_hour(scheduled_send_date)

    for b in generated_message_autobumps:
        bump: GeneratedMessageAutoBump = b

        if bump.prospect_id in sent_prospect_ids:
            continue

        sent_prospect_ids.add(bump.prospect_id)

        prospect: Prospect = Prospect.query.get(bump.prospect_id)

        print("Scheduling " + prospect.full_name)

        add_process_for_future(
            type="send_scheduled_linkedin_message",
            args={
                "client_sdr_id": client_sdr_id,
                "prospect_id": bump.prospect_id,
                "message": bump.message,
                "send_sellscale_notification": True,
                "ai_generated": True,
                "bf_id": bump.bump_framework_id,
                "bf_title": bump.bump_framework_title,
                "bf_description": bump.bump_framework_description,
                "bf_length": bump.bump_framework_length
                and bump.bump_framework_length.value,
                "account_research_points": bump.account_research_points,
                "to_purgatory": True,
                "purgatory_date": (scheduled_send_date).isoformat(),
            },
            relative_time=scheduled_send_date,
        )

        prospect.hidden_until = scheduled_send_date + timedelta(days=3)
        db.session.add(prospect)
        db.session.commit()

        scheduled_send_date += timedelta(minutes=15)
        scheduled_send_date = next_business_hour(scheduled_send_date)


def create_cta_asset_mapping(generated_message_cta_id: int, client_assets_id: int):
    mapping: GeneratedMessageCTAToAssetMapping = GeneratedMessageCTAToAssetMapping(
        generated_message_cta_id=generated_message_cta_id,
        client_assets_id=client_assets_id,
    )
    db.session.add(mapping)
    db.session.commit()
    return True


def delete_cta_asset_mapping(
    cta_to_asset_mapping_id: int,
):
    mapping: GeneratedMessageCTAToAssetMapping = (
        GeneratedMessageCTAToAssetMapping.query.get(cta_to_asset_mapping_id)
    )
    if not mapping:
        return True

    db.session.delete(mapping)
    db.session.commit()
    return True


def get_all_cta_assets(generated_message_cta_id: int):
    mappings: list[
        GeneratedMessageCTAToAssetMapping
    ] = GeneratedMessageCTAToAssetMapping.query.filter(
        GeneratedMessageCTAToAssetMapping.generated_message_cta_id
        == generated_message_cta_id
    ).all()
    asset_ids = [mapping.client_assets_id for mapping in mappings]
    assets: list[ClientAssets] = ClientAssets.query.filter(
        ClientAssets.id.in_(asset_ids)
    ).all()
    asset_dicts = [asset.to_dict() for asset in assets]

    # add 'mapping_id' to each asset
    for i, asset in enumerate(asset_dicts):
        correct_mapping = next(
            mapping for mapping in mappings if mapping.client_assets_id == asset["id"]
        )
        asset["mapping_id"] = correct_mapping.id

    return asset_dicts
