from datetime import datetime
from typing import Dict, List, Optional, Union

from bs4 import BeautifulSoup
from src.email_outbound.models import ProspectEmailOutreachStatus, ProspectEmailStatus
from src.ml.openai_wrappers import DEFAULT_TEMPERATURE, OPENAI_CHAT_GPT_4_TURBO_MODEL
from src.li_conversation.models import LinkedInConvoMessage
from src.bump_framework.models import BumpFramework
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate

from src.research.models import IScraperPayloadCache, ResearchPoints
from src.research.models import ResearchPayload

from src.research.models import AccountResearchPoints
from app import db, celery
import os
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect, ProspectStatus
from src.message_generation.models import (
    GeneratedMessage,
    GeneratedMessageEmailType,
    GeneratedMessageType,
)
from src.ml.models import (
    GNLPFinetuneJobStatuses,
    GNLPModel,
    GNLPModelFineTuneJobs,
    GNLPModelType,
    ModelProvider,
    TextGeneration,
)
import traceback

from src.ml.openai_wrappers import (
    wrapped_create_completion,
    wrapped_chat_gpt_completion,
    OPENAI_COMPLETION_DAVINCI_3_MODEL,
    OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
    OPENAI_CHAT_GPT_4_MODEL,
)
import regex as rx
import re
import math
import openai
import json
import yaml
from src.company.services import find_company_for_prospect
from src.utils.abstract.attr_utils import deep_get


DEFAULT_MONTHLY_ML_FETCHING_CREDITS = 5000


def remove_control_characters(str):
    return rx.sub(r"\p{C}", "", str)


def create_upload_jsonl_file(prompt_completion_dict: any):
    with open("training_set_temp.jsonl", "w") as f:
        for key in prompt_completion_dict:
            sanitized_key = remove_control_characters(
                key.replace('"', "")
                .replace("\n", "\\n")
                .replace("\r", "")
                .replace("\\", "")
            )
            sanitized_value = prompt_completion_dict[key].replace('"', "")

            f.write(
                "{"
                + '"prompt":"{}","completion":"{} XXX"'.format(
                    sanitized_key, sanitized_value
                )
                .replace("\n", "\\n")
                .replace("\r", "")
                .replace("\\", "")
                + "}\n"
            )
        f.close()

    jsonl_file_upload = openai.File.create(
        file=open("training_set_temp.jsonl"), purpose="fine-tune"
    )
    return jsonl_file_upload


def initiate_fine_tune_job(
    archetype_id: int, message_ids: list, model_type: GNLPModelType
):
    # create new fine tune job in db
    job: GNLPModelFineTuneJobs = GNLPModelFineTuneJobs(
        archetype_id=archetype_id,
        message_ids=message_ids,
        status=GNLPFinetuneJobStatuses.INITIATED,
        model_type=model_type,
    )
    db.session.add(job)
    db.session.commit()
    try:
        # upload jsonl file
        messages: list[GeneratedMessage] = GeneratedMessage.query.filter(
            GeneratedMessage.id.in_(message_ids)
        ).all()
        prompt_completion_dict = {m.prompt: m.completion for m in messages}
        jsonl_file_upload_resp = create_upload_jsonl_file(
            prompt_completion_dict=prompt_completion_dict
        )
        file_id = jsonl_file_upload_resp["id"]
        job.jsonl_file_id = file_id
        job.jsonl_file_response = jsonl_file_upload_resp
        job.status = GNLPFinetuneJobStatuses.UPLOADED_JSONL_FILE
        db.session.add(job)
        db.session.commit()

        # create new finetune job
        fine_tune_create_job_resp = openai.FineTune.create(
            training_file=file_id, model="davinci"
        )
        fine_tune_job_id = fine_tune_create_job_resp["id"]
        job.finetune_job_id = fine_tune_job_id
        job.finetune_job_response = fine_tune_create_job_resp
        job.status = GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
        db.session.add(job)
        db.session.commit()

        return True, "OK"
    except Exception as e:
        # if failed update status
        job.status = GNLPFinetuneJobStatuses.FAILED
        job.error = str(e)
        db.session.add(job)
        db.session.commit()

        return False, str(e)


# Deprecated
# @celery.task
# def check_statuses_of_fine_tune_jobs():
#     jobs: list = GNLPModelFineTuneJobs.query.filter(
#         GNLPModelFineTuneJobs.status == GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
#     ).all()

#     updated_job_ids = []
#     for j in jobs:
#         job: GNLPModelFineTuneJobs = j
#         archetype: ClientArchetype = ClientArchetype.query.get(job.archetype_id)
#         archetype_id = archetype.id
#         archetype_name = archetype.archetype

#         fine_tune_status = get_fine_tune_timeline(fine_tune_id=job.finetune_job_id)
#         model_uuid = fine_tune_status.get("fine_tuned_model")

#         client: Client = Client.query.get(archetype.client_id)

#         if model_uuid:
#             gnlp_model: GNLPModel = GNLPModel(
#                 model_provider=ModelProvider.OPENAI_GPT3,
#                 model_type=job.model_type,
#                 model_description="{client}-{archetype_name}-{date}".format(
#                     client=client.company,
#                     archetype_name=archetype_name,
#                     date=str(datetime.utcnow())[0:10],
#                 ),
#                 model_uuid=model_uuid,
#                 archetype_id=archetype_id,
#             )
#             db.session.add(gnlp_model)
#             db.session.commit()

#             gnlp_model_id = gnlp_model.id

#             job.gnlp_model_id = gnlp_model_id
#             job.status = GNLPFinetuneJobStatuses.COMPLETED
#             db.session.add(job)
#             db.session.commit()

#             updated_job_ids.append(job.id)

#     print("checked fine tuned job statuses.")

#     return updated_job_ids


def get_fine_tune_timeline(fine_tune_id: str):
    from model_import import GNLPModelFineTuneJobs

    response = openai.FineTune.retrieve(id=fine_tune_id)
    job: GNLPModelFineTuneJobs = GNLPModelFineTuneJobs.query.filter(
        GNLPModelFineTuneJobs.finetune_job_id == fine_tune_id
    ).first()
    job.finetune_job_response = response
    db.session.add(job)
    db.session.commit()

    return response


def create_profane_word(words: str):
    from model_import import ProfaneWords

    word_exists = ProfaneWords.query.filter(ProfaneWords.words == words).first()
    if word_exists:
        return word_exists

    profane_word = ProfaneWords(words=words)
    db.session.add(profane_word)
    db.session.commit()

    return profane_word


def contains_profane_word(text: str):
    d = db.session.execute(
        """select array_agg(profane_words.words) from profane_words"""
    ).fetchall()[0][0]
    regex = re.compile("(?=(" + "|".join(map(re.escape, d)) + "))")
    matches = re.findall(regex, text)

    if len(matches) > 0:
        return False, []

    return True, matches


def get_aree_fix_basic(
    message_id: Optional[int] = None,
    completion: Optional[str] = None,
    problems: Optional[list[str]] = [],
) -> str:
    """Gets the ARREE Fix (Basic). Either a message_id or completion must be provided.

    Args:
        message_id (int): _description_
        completion (Optional[str], optional): _description_. Defaults to None.
        problems (Optional[list[str]], optional): _description_. Defaults to None.

    Returns:
        str: _description_
    """
    if not message_id and not completion:
        return ""

    message = None
    if message_id:
        message: Optional[GeneratedMessage] = GeneratedMessage.query.get(message_id)
        if not message:
            return "Message not found"
        problems = message.problems
        if not problems:
            return message.completion
        completion = message.completion.strip()

    # Format the problems in a bulleted list
    problems_bulleted = ""
    for p in problems:
        problems_bulleted += f"- {p}\n"

    # Create the instruction
    instruction = """Given the message and a list of problems identified in the message, please fix the message. Make as few changes as possible."""
    if message and message.message_type == GeneratedMessageType.EMAIL:
        # If the message is an Email
        if message.email_type == GeneratedMessageEmailType.BODY:
            template_id = message.email_sequence_step_template_id
            template: EmailSequenceStep = EmailSequenceStep.query.get(template_id)
            template = template.template
        elif message.email_type == GeneratedMessageEmailType.SUBJECT_LINE:
            subject_line_id = message.email_subject_line_template_id
            subject_line: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.get(
                subject_line_id
            )
            template = subject_line.subject_line

        instruction = """Given the email and a list of problems identified in the email, please fix the email. Make as few changes as possible.

This template was used to generate the email. Do not deviate from the template:
=== START EMAIL TEMPLATE ===
{template}
=== END EMAIL TEMPLATE ===
""".format(
            template=template
        )

    # Construct the final prompt
    prompt = """Message:
"{completion}"

Problems:
{problems_bulleted}

Instruction: {instruction}

Important: Return only the revised message with the problems fixed. Do not include the original message or the problems in the output.

Output:""".format(
        completion=completion,
        problems_bulleted=problems_bulleted,
        instruction=instruction,
    )

    # Get the fixed completion
    fixed_completion = wrapped_chat_gpt_completion(
        model=OPENAI_CHAT_GPT_4_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=len(completion) + 10,
    )

    if (
        "Problems:" in fixed_completion
        or "Instruction:" in fixed_completion
        or "===" in fixed_completion
    ):
        return completion

    # if has surrounding quotes, remove
    if fixed_completion[0] == '"' and fixed_completion[-1] == '"':
        fixed_completion = fixed_completion[1:-1]
    if fixed_completion[0] == "'" and fixed_completion[-1] == "'":
        fixed_completion = fixed_completion[1:-1]

    return fixed_completion


def get_sequence_value_props(
    company: str, selling_to: str, selling_what: str, num: int
):
    prompt = f"You are a writing assistant that helps write email sequences. Here is the information:\n"
    prompt += f"- Company: {company}\n"
    prompt += f"- Who are you selling to?: {selling_to}\n"
    prompt += f"- What are you selling?: {selling_what}\n"
    prompt += f"- Number of emails in the sequence: {num}\n"
    prompt += "\n\nBased on this information, generate {num} value props we can use to target. Each value prop should be a 5-10 word phrase with a hyphen and one sentance describing it in detail.".format(
        num=num
    )

    fixed_completion = wrapped_create_completion(
        model=OPENAI_COMPLETION_DAVINCI_3_MODEL,
        prompt=prompt,
        temperature=1,
        max_tokens=20 + 30 * num,
    )

    print(fixed_completion)
    props = re.sub(r"\d+\. ", "", fixed_completion).split("\n")
    print(props)
    return props


def get_icp_classification_prompt_by_archetype_id(archetype_id: int) -> str:
    """Gets the ICP Classification Prompt for a given archetype id.

    Args:
        archetype_id (int): The archetype id.

    Returns:
        str: The prompt and filters.
    """
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return None

    return archetype.icp_matching_prompt, archetype.icp_matching_option_filters


def send_icp_classification_change_message(
    sdr_name: str, archetype: str, archetype_id: int, new_prompt: str
):
    from src.automation.slack_notification import send_slack_message, URL_MAP

    message_sent = send_slack_message(
        message="ICP Classification Prompt Change Requested",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Pulse Prompt Changed - {sdr}".format(sdr=sdr_name),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Persona: {persona} ({archetype_id})".format(
                            persona=archetype, archetype_id=archetype_id
                        ),
                    }
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "New Prompt:\n\n{new_prompt}".format(new_prompt=new_prompt),
                },
            },
        ],
        webhook_urls=[URL_MAP.get("operations-pulse-change")],
    )
    if not message_sent:
        return False, "Failed to send update request."

    return True, "Success"


def patch_icp_classification_prompt(
    archetype_id: int,
    prompt: str,
    send_slack_message: Optional[bool] = False,
    option_filters: Optional[dict] = None,
) -> bool:
    """Modifies the ICP Classification Prompt for a given archetype id.

    Args:
        archetype_id (int): The archetype id.
        prompt (str): The new prompt.

    Returns:
        bool: True if successful, False otherwise.
    """
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return False
    sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)

    archetype.icp_matching_prompt = prompt

    if option_filters:
        archetype.icp_matching_option_filters = option_filters

    db.session.add(archetype)
    db.session.commit()

    if send_slack_message:
        send_icp_classification_change_message(
            sdr_name=sdr.name,
            archetype=archetype.archetype,
            archetype_id=archetype.id,
            new_prompt=prompt,
        )

    return True, prompt


def trigger_icp_classification(
    client_sdr_id: int, archetype_id: int, prospect_ids: list[int]
) -> bool:
    """Triggers the ICP Classification Endpoint for a given client SDR id and archetype id.

    Args (used to verify the client SDR id and archetype id):
        client_sdr_id (int): The client SDR id.
        archetype_id (int): The archetype id.
        prospect_ids (List[int]): The prospect ids.

    Returns:
        bool: True if successful, False otherwise.
    """
    if len(prospect_ids) > 0:
        # Run celery job for each prospect id
        for index, prospect_id in enumerate(prospect_ids):
            countdown = float(index * 6)
            mark_queued_and_classify.apply_async(
                args=[client_sdr_id, archetype_id, prospect_id, countdown],
                queue="icp_scoring",
                routing_key="icp_scoring",
                priority=1,
            )
    else:
        # Get all prospects for the client SDR id and archetype id
        prospects: list[Prospect] = Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.archetype_id == archetype_id,
        ).all()

        # Run celery job for each prospect
        for index, prospect in enumerate(prospects):
            prospect_id = prospect.id
            countdown = float(index * 6)
            mark_queued_and_classify.apply_async(
                args=[client_sdr_id, archetype_id, prospect_id, countdown],
                queue="icp_scoring",
                routing_key="icp_scoring",
                priority=1,
            )
    return True


def trigger_icp_classification_single_prospect(
    client_sdr_id: int, archetype_id: int, prospect_id: int
) -> tuple[str, str]:
    """Triggers the ICP Classification Endpoint for a given client SDR id and archetype id.

    Args:
        client_sdr_id (int): The client SDR id.
        archetype_id (int): The archetype id.
        prospect_id (int): The prospect id.

    Returns:
        tuple(str, str): The fit and reason.
    """
    try:
        fit = -1  # -1 fit means the prospect had an error, and we should try again
        retries = 3  # Number of times to try to classify the prospect
        attempts = 0  # Number of attempts to classify the prospect
        while fit < 0 and attempts < retries:
            fit, reason = icp_classify(
                prospect_id=prospect_id,
                client_sdr_id=client_sdr_id,
                archetype_id=archetype_id,
            )
            attempts += 1
        return fit, reason
    except:
        return "ERROR", "Failed to classify prospect."


@celery.task(bind=True, max_retries=2)
def mark_queued_and_classify(
    self, client_sdr_id: int, archetype_id: int, prospect_id: int, countdown: float
) -> bool:
    """Marks a prospect as QUEUED and then ICP classifies it.

    Args:
        client_sdr_id (int): ID of the client SDR
        archetype_id (int): ID of the archetype
        prospect_id (int): ID of the prospect
        countdown (float): Number of seconds to wait before running the task

    Returns:
        bool: True if successful, False otherwise.
    """
    prospect: Prospect = Prospect.query.filter(
        Prospect.id == prospect_id,
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.archetype_id == archetype_id,
    ).first()
    if not prospect:
        return False

    # Mark Prospect as QUEUED
    prospect.icp_fit_score = -3
    prospect.icp_fit_reason = "Queued for ICP Fit Score Calculation"
    db.session.add(prospect)
    db.session.commit()

    # Classify Prospect
    icp_classify.apply_async(
        args=[prospect.id, client_sdr_id, archetype_id],
        countdown=countdown,
        queue="icp_scoring",
        routing_key="icp_scoring",
        priority=2,
    )

    return True


@celery.task(bind=True, max_retries=3)
def icp_classify(  # DO NOT RENAME THIS FUNCTION, IT IS RATE LIMITED IN APP.PY BY CELERY
    self, prospect_id: int, client_sdr_id: int, archetype_id: int
) -> tuple[int, str]:
    """Classifies a prospect as an ICP or not.

    Args:
        prospect_id (int): The prospect id.
        client_sdr_id (int): The client SDR id.
        archetype_id (int): The archetype id.

    Returns:
        tuple(int, str): The ICP fit score and reason.
    """
    from src.prospecting.upload.services import run_and_assign_intent_score

    try:
        # Get Prospect
        prospect: Prospect = Prospect.query.filter(
            Prospect.id == prospect_id,
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.archetype_id == archetype_id,
        ).first()
        if not prospect:
            return False

        # Check for ML credit limit
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        if client_sdr.ml_credits <= 0:
            # Mark Prospect as NO CREDITS
            prospect.icp_fit_score = -3
            prospect.icp_fit_reason = "No more account research credits."
            db.session.add(prospect)
            db.session.commit()
            return False, "No more account research credits."

        # Checkpoint: Mark Prospect as IN PROGRESS
        prospect.icp_fit_score = -2
        prospect.icp_fit_reason = "ICP Fit Score Calculation in Progress"
        db.session.add(prospect)
        db.session.commit()

        # Reretrieve the Prospect
        prospect: Prospect = Prospect.query.filter(
            Prospect.id == prospect_id,
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.archetype_id == archetype_id,
        ).first()

        # Get Archetype for prompt
        archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
        icp = archetype.icp_matching_prompt
        if not icp or icp.strip() == "":
            prospect.icp_fit_score = -1
            prospect.icp_fit_reason = "No ICP Classification Prompt"
            db.session.add(prospect)
            db.session.commit()
            return False

        prompt = HARD_CODE_ICP_HEADER
        prompt += icp

        # Get Company Description
        company = find_company_for_prospect(prospect_id)
        prospect_company_description = company.description if company else ""
        prospect_company_specialities = company.specialities if company else ""

        state = "Location unknown."
        if company:
            location = company.locations
            state = (
                str(location[0]) if location and location[0] else "Location unknown."
            )

        iscraper_cache: IScraperPayloadCache = (
            IScraperPayloadCache.get_iscraper_payload_cache_by_linkedin_url(
                linkedin_url=prospect.linkedin_url
            )
        )

        prospect_location = "Prospect location unknown."
        prospect_education = "Prospect school and degree unknown."
        cache = (
            json.loads(iscraper_cache.payload)
            if iscraper_cache and iscraper_cache.payload
            else None
        )
        if cache and cache.get("location"):
            prospect_location = cache.get("location")
        if cache and cache.get("education") and len(cache.get("education")) > 0:
            school = cache.get("education")[0].get("school")
            school_name = deep_get(cache, "education.0.school.name")
            field_of_study = deep_get(cache, "education.0.field_of_study")
            prospect_education = "Studied {field_of_study} at {school_name}".format(
                field_of_study=field_of_study, school_name=school_name
            )

        # Create Prompt
        if archetype.icp_matching_option_filters:
            prompt += f"\n\nHere is the prospect's information:"
            if archetype.icp_matching_option_filters.get("prospect_name"):
                prompt += f"\nProspect Name: {prospect.full_name}"
            if archetype.icp_matching_option_filters.get("prospect_title"):
                prompt += f"\nProspect Title: {prospect.title}"
            if archetype.icp_matching_option_filters.get("prospect_linkedin_bio"):
                prompt += f"\nProspect LinkedIn Bio: {prospect.linkedin_bio}"
            if archetype.icp_matching_option_filters.get("prospect_location"):
                prompt += f"\nProspect Location: {prospect_location}"
            if archetype.icp_matching_option_filters.get("prospect_education"):
                prompt += f"\nProspect Education: {prospect_education}"

            prompt += f"\n\nHere is the prospect's company information:"
            if archetype.icp_matching_option_filters.get("company_name"):
                prompt += f"\nProspect Company Name: {prospect.company}"
            if archetype.icp_matching_option_filters.get("company_size"):
                prompt += f"\nProspect Company Size: {prospect.employee_count}"
            if archetype.icp_matching_option_filters.get("company_industry"):
                prompt += f"\nProspect Company Industry: {prospect.industry}"
            if archetype.icp_matching_option_filters.get("company_location"):
                prompt += f"\nProspect Company Location: {state}"
            if archetype.icp_matching_option_filters.get("company_tagline"):
                prompt += f"\nProspect Company Tagline: {prospect_company_specialities}"
            if archetype.icp_matching_option_filters.get("company_description"):
                prompt += f"\nProspect Company Description: '''\n{prospect_company_description}\n'''"
        else:
            prompt += f"""\n\nHere is the prospect's information:
            Prospect Name: {prospect.full_name}
            Prospect Title: {prospect.title}
            Prospect LinkedIn Bio: {prospect.linkedin_bio}
            Prospect Location: {prospect_location}
            Prospect Education: {prospect_education}

            Here is the prospect's company information:
            Prospect Company Name: {prospect.company}
            Prospect Company Size: {prospect.employee_count}
            Prospect Company Industry: {prospect.industry}
            Prospect Company Location: {state}
            Prospect Company Tagline: {prospect_company_specialities}
            Prospect Company Description: '''
            {prospect_company_description}
            '''\n\n"""

        # print(prompt)

        prompt += HARD_CODE_ICP_PROMPT

        # Generate Completion
        completion = get_text_generation(
            [{"role": "user", "content": prompt}],
            max_tokens=100,
            model=OPENAI_CHAT_GPT_4_MODEL,
            type="ICP_CLASSIFY",
            prospect_id=prospect_id,
            client_sdr_id=client_sdr_id,
        )
        fit = completion.split("Fit:")[1].split("Reason:")[0].strip()
        fit = int(fit)
        reason = completion.split("Reason:")[1].strip()

        # Update Prospect
        prospect.icp_fit_score = fit
        prospect.icp_fit_reason = reason
        prospect.icp_fit_prompt_data = prompt

        # Charge the SDR credits
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client_sdr.ml_credits -= 1

        db.session.add_all([client_sdr, prospect])
        db.session.commit()

        run_and_assign_intent_score(prospect_id)
        return fit, reason

    except Exception as e:
        from src.utils.slack import send_slack_message, URL_MAP

        stack_trace = traceback.format_exc()
        send_slack_message(
            message=f"Error when classifying prospect {prospect_id} for archetype {archetype_id}: {str(e)}\n{stack_trace}",
            webhook_urls=[URL_MAP["eng-icp-errors"]],
        )

        db.session.rollback()

        prospect: Prospect = Prospect.query.filter(
            Prospect.id == prospect_id,
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.archetype_id == archetype_id,
        ).first()
        if not prospect:
            return False
        prospect.icp_fit_score = -1
        prospect.icp_fit_reason = "Error Calculating ICP Fit Score. Please try again."
        prospect.icp_fit_error = f"Unknown Error: {e}"
        db.session.add(prospect)
        db.session.commit()

        raise self.retry(exc=e, countdown=15**self.request.retries)


HARD_CODE_ICP_HEADER = "I am a sales researcher. This is the Ideal Customer Profile for my target customer:\n\n"


HARD_CODE_ICP_PROMPT = """Based on this information, label the person based on if they are the ideal ICP using:

- "4" - They are very much the right fit
- "3" - They are likely the right fit
- “2” - they may be the right fit
- "1" - They are unlikely to be the right fit
- “0” - They are most probably not the right fit.

Include this numeric label next to the word "Fit:" based on if this person is the ideal ICP. Then add a new line and say "Reason:" with 1-2 sentences describing why this label was chosen.

Example:
Fit: 1
Reason: Some reason
"""


def edit_text(initial_text: str, edit_prompt: str) -> str:
    system_prompt = """
You are an editing assistant. You are helping a writer edit their text.
    """
    user_prompt = """
The writer has written the following text:
{initial_text}

The writer has given you the following prompt to edit the text:
{edit_prompt}

Make the requested edits.

Edited Text:""".format(
        initial_text=initial_text, edit_prompt=edit_prompt
    )
    response = get_text_generation(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=int(len(initial_text) / 4) + 100,
        model=OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
        type="TEXT_EDITOR",
    )
    return response


def replenish_all_ml_credits_for_all_sdrs() -> bool:
    """Replenishes all ML credits for all SDRs."""
    sdrs: list[ClientSDR] = ClientSDR.query.filter_by(
        active=True,
    )
    for sdr in sdrs:
        sdr.ml_credits = 5000
        db.session.add(sdr)

    db.session.commit()

    return True


def chat_ai_verify_scheduling_convo(messages: list[str], seller: str) -> bool:
    """Verifies if the conversation is about scheduling a meeting.

    Args:
        messages (list[str]): The conversation history.
        seller (str): The name of the seller.

    Returns:
        bool: Whether the conversation is about scheduling a meeting.
    """
    # Construct the transcript
    transcript = ""
    for message in messages:
        transcript += message + "\n\n"

    prompt = """The following transcript was determined to feature a seller and a potential customer discussing a time to meet. The following transcript was thus classified as "SCHEDULING".

Can you confirm, by replying either 0 (for False) or 1 (for True) that this conversation meets the following criteria for "SCHEDULING."

Criteria (one or the other):
1. Both parties are actively engaged in finding a time to meet.
2. The customer is showing a willingness to schedule a call.

Seller: {seller_name}

--- Start Transcript ---
{transcript}
--- End Transcript ---
""".format(
        seller_name=seller, transcript=transcript
    )

    response = get_text_generation(
        [{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
        model=OPENAI_CHAT_GPT_4_MODEL,
        type="MISC_CLASSIFY",
    )

    match = re.search(r"\d+", response)
    if match:
        number = int(match.group(0))
    else:
        return False

    return number == 1


def chat_ai_classify_active_convo(messages: list[str], seller: str) -> ProspectStatus:
    """Selects one of the following options based on the conversation history.

    Args:
        messages: The conversation history.
        seller: The name of the seller.

    Returns:
        The index of the selected option.
    """
    # Construct the transcript
    transcript = ""
    for message in messages:
        transcript += message + "\n\n"

    prompt = """I have a transcript of a conversation below between a seller and potential customer. Help me classify the conversation based on the most recent messages. Please classify the conversation as one of the following options, provide just the number and nothing else.

1. MORE_ENGAGEMENT: The conversation needs more engagement from the seller
2. OBJECTION: There is an objection or abrasion about a product or service from the customer. Or the customer states that they are completely not interested. Or the customer states that they are not the best person to contact.
3. QUESTION: There is a question from the customer
4. CIRCLE_BACK: The customer has stated that now is not a good time and that the seller should reach out at a later time.
5. REFERRAL: The customer is referring the seller to a different contact
6. OTHER: Some other conversation

Seller: {seller_name}

--- Begin Transcript ---
{transcript}
--- End Transcript ---
""".format(
        seller_name=seller, transcript=transcript
    )

    response = get_text_generation(
        [{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
        model=OPENAI_CHAT_GPT_4_MODEL,
        type="MISC_CLASSIFY",
    )

    match = re.search(r"\d+", response)
    if match:
        number = int(match.group(0))
    else:
        return ProspectStatus.ACTIVE_CONVO_NEXT_STEPS

    cases = {
        1: ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        2: ProspectStatus.ACTIVE_CONVO_OBJECTION,
        3: ProspectStatus.ACTIVE_CONVO_QUESTION,
        4: ProspectStatus.ACTIVE_CONVO_CIRCLE_BACK,
        5: ProspectStatus.ACTIVE_CONVO_REFERRAL,
        6: ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
    }
    return cases.get(number, ProspectStatus.ACTIVE_CONVO_NEXT_STEPS)


def chat_ai_classify_email_active_convo(message: str) -> ProspectEmailOutreachStatus:
    """Selects one of the following options based on the reply message.

    Args:
        message: The message.

    Returns:
        The index of the selected option.
    """
    prompt = """I have a message from a potential customer to a seller. Help me classify the message. Please classify the message as one of the following options, provide just the number and nothing else.

1. MORE_ENGAGEMENT: The conversation needs more engagement from the seller
2. OBJECTION: There is an objection or abrasion about a product or service from the customer. Or the customer states that they are completely not interested. Or the customer states that they are not the best person to contact.
3. QUESTION: There is a question from the customer
4. CIRCLE_BACK: The customer has stated that now is not a good time and that the seller should reach out at a later time.
5. REFERRAL: The customer is referring the seller to a different contact
6. SCHEDULING: The customer is discussing a time to meet
7. OTHER: Some other conversation

--- BEGIN MESSAGE ---
{message}
--- END MESSAGE ---

Provide your answer in the following JSON Format:
{{"classification": 1}}

The JSON output:
""".format(
        message=message
    )

    response = wrapped_chat_gpt_completion(
        [{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
        model=OPENAI_CHAT_GPT_4_MODEL,
    )

    try:
        json_response: dict = yaml.safe_load(response)
    except:
        return ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS

    number = json_response.get("classification", 7)
    cases = {
        1: ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        2: ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        3: ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        4: ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        5: ProspectEmailOutreachStatus.ACTIVE_CONVO_REFERRAL,
        6: ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        7: ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
    }
    return cases.get(number, ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS)


def determine_account_research_from_convo_and_bump_framework(
    prospect_id: int,
    convo_history: List[Dict[str, str]],
    bump_framework_desc: str,
    account_research: List[str],
):
    """Determines the account research points from the conversation and bumps the framework."""

    prospect: Prospect = Prospect.query.get(prospect_id)

    messages = [
        {
            "role": "system",
            "content": f"You are a helpful assistant named {prospect.full_name}.",
        }
    ]
    for message in convo_history:
        messages.append(
            {
                "role": (
                    "user" if message.get("connection_degree") == "You" else "assistant"
                ),
                "content": message.get("message", ""),
            }
        )

    options = ""
    for i, option in enumerate(account_research):
        options += f"- {i+1}. {option}\n"

    messages.append(
        {
            "role": "user",
            "content": f"""
    Based on the following topic and our previous conversation history, please select 0 to 3 pieces of research that are the most relevant and fitting for a follow-up message of the given topic's premise. Respond only with an number array of the selected research points. If no pieces of research seem fitting, feel free to return an empty array.

    ## Topic
    {bump_framework_desc}

    ## Research
    {options}
    """,
        }
    )

    response = get_text_generation(
        messages,
        temperature=0.65,
        max_tokens=240,
        model="gpt-3.5-turbo-16k",
        type="MISC_CLASSIFY",
    )

    # Extract the numbers from the response & convert to index
    numbers = re.findall(r"\d+", response)
    numbers = [int(number) - 1 for number in numbers]

    return numbers


def determine_best_bump_framework_from_convo(
    convo_history: List[LinkedInConvoMessage], bump_framework_ids: List[str]
):
    """Determines the best bump framework from the conversation."""

    bump_frameworks = []
    for bump_framework_id in bump_framework_ids:
        bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
        if bump_framework:
            bump_frameworks.append(
                {
                    "description": bump_framework.description,
                    "default": bump_framework.default,
                }
            )

    default_indexes = []
    for i, bump_framework in enumerate(bump_frameworks):
        if bump_framework.get("default"):
            default_indexes.append(i)

    if len(default_indexes) >= len(convo_history) - 1 and len(default_indexes) > 0:
        return default_indexes[len(convo_history) - 2]

    if len(default_indexes) > 0:
        return default_indexes[0]

    messages = []
    for message in convo_history[::-1]:
        messages.append(
            {
                "role": "user" if message.connection_degree == "You" else "assistant",
                "content": message.message,
            }
        )

    options = ""
    for i, option in enumerate(bump_frameworks):
        options += f"- {i+1}. {option['description']}\n"

    messages.append(
        {
            "role": "user",
            "content": f"""
    Based on our previous conversation history, please select the best response description to continue the conversation. Respond only with the option number.

    ## Response Descriptions
    {options}
    """,
        }
    )

    response = get_text_generation(
        messages,
        temperature=0.65,
        max_tokens=240,
        model="gpt-3.5-turbo-16k",
        type="MISC_CLASSIFY",
    )

    match = re.search(r"\d+", response)
    if match:
        return int(match.group()) - 1
    else:
        return -1


def get_text_generation(
    messages: list,
    type: str,
    model: str,
    max_tokens: int,
    prospect_id: Optional[int] = None,
    client_sdr_id: Optional[int] = None,
    temperature: Optional[float] = DEFAULT_TEMPERATURE,
    use_cache: bool = False,
    tools: Optional[list] = None,
) -> Optional[str]:
    # type = "LI_MSG_INIT" | "LI_MSG_OTHER" | "RESEARCH" | "EMAIL" | "VOICE_MSG" | "ICP_CLASSIFY"
    # | "TEXT_EDITOR" | "MISC_CLASSIFY" | "MISC_SUMMARIZE" | "LI_CTA" | "CLIENT_ASSETS"

    def normalize_string(string: str) -> str:
        string = re.sub(r"\\n", " ", string)
        string = string.strip()  # Remove leading/trailing whitespace
        string = " ".join(string.split())
        return string

    try:
        json_msgs = normalize_string(json.dumps(messages))
    except Exception as e:
        json_msgs = None

    text_gen = None
    if use_cache:
        text_gen: TextGeneration = TextGeneration.query.filter(
            TextGeneration.prompt == json_msgs,
        ).first()

    if json_msgs and text_gen:
        return text_gen.completion
    else:
        response = wrapped_chat_gpt_completion(
            messages,
            max_tokens=max_tokens,
            model=model,
            temperature=temperature,
            tools=tools,
        )
        if not json_msgs:
            return response

        if isinstance(response, str):
            text_gen = TextGeneration(
                prompt=json_msgs,
                completion=response,
                type=type,
                model_provider=model,
                prospect_id=prospect_id,
                client_sdr_id=client_sdr_id,
                human_edited=False,
                status="GENERATED",
            )

            db.session.add(text_gen)
            db.session.commit()

            return response

        else:
            return ""


def detect_hallucinations(
    message_prompt: str, message: str, attempts: Optional[int] = 2
) -> list[str]:
    """Detects hallucinations in a generated message.

    Args:
        message_prompt (str): The message prompt.
        message (str): The generated message.
        attempts (int): The number of attempts to try.

    Returns:
        list[str]: The hallucinations.
    """
    attempts -= 1

    system_instructions = "You are an assistant that will help me detect hallucinations. A hallucination is defined as messaging that references entities that were not present in the original prompt."
    prompt = """Help me determine if there are any hallucinations in the following generated message. A hallucination is defined as messaging that references entities that were not present in the original prompt.

==== START PROMPT ====
{message_prompt}
==== END PROMPT ====

==== START MESSAGE ====
{message}
==== END MESSAGE ====

Please return a JSON object such as the following:
{{
    "hallucinations": ["Apple", "U.S. Air Force"]
}}
Just return the JSON string object, no prose. Do not include ```json. We will use json.loads().

If there are no hallucinations, just return an empty list

Output:
""".format(
        message_prompt=message_prompt, message=message
    )

    try:
        response = wrapped_chat_gpt_completion(
            [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": prompt},
            ],
            max_tokens=100,
            model=OPENAI_CHAT_GPT_4_TURBO_MODEL,
        )
        response = yaml.safe_load(response)

        hallucinations = response.get("hallucinations", [])
    except Exception as e:
        if attempts > 0:
            return detect_hallucinations(message_prompt, message, attempts)

        return []

    return hallucinations
