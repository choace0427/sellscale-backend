from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from src.li_conversation.models import LinkedInConvoMessage
from src.bump_framework.models import BumpFramework
from src.bump_framework_email.models import BumpFrameworkEmail

from src.research.models import IScraperPayloadCache, ResearchPoints
from src.research.models import ResearchPayload

from src.research.models import AccountResearchPoints
from app import db, celery
import os
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect, ProspectStatus
from src.message_generation.models import GeneratedMessage
from src.ml.models import (
    GNLPFinetuneJobStatuses,
    GNLPModel,
    GNLPModelFineTuneJobs,
    GNLPModelType,
    ModelProvider,
)

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


@celery.task
def check_statuses_of_fine_tune_jobs():
    jobs: list = GNLPModelFineTuneJobs.query.filter(
        GNLPModelFineTuneJobs.status == GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
    ).all()

    updated_job_ids = []
    for j in jobs:
        job: GNLPModelFineTuneJobs = j
        archetype: ClientArchetype = ClientArchetype.query.get(job.archetype_id)
        archetype_id = archetype.id
        archetype_name = archetype.archetype

        fine_tune_status = get_fine_tune_timeline(fine_tune_id=job.finetune_job_id)
        model_uuid = fine_tune_status.get("fine_tuned_model")

        client: Client = Client.query.get(archetype.client_id)

        if model_uuid:
            gnlp_model: GNLPModel = GNLPModel(
                model_provider=ModelProvider.OPENAI_GPT3,
                model_type=job.model_type,
                model_description="{client}-{archetype_name}-{date}".format(
                    client=client.company,
                    archetype_name=archetype_name,
                    date=str(datetime.utcnow())[0:10],
                ),
                model_uuid=model_uuid,
                archetype_id=archetype_id,
            )
            db.session.add(gnlp_model)
            db.session.commit()

            gnlp_model_id = gnlp_model.id

            job.gnlp_model_id = gnlp_model_id
            job.status = GNLPFinetuneJobStatuses.COMPLETED
            db.session.add(job)
            db.session.commit()

            updated_job_ids.append(job.id)

    print("checked fine tuned job statuses.")

    return updated_job_ids


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


def get_aree_fix_basic(message_id: int) -> str:
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    if not message:
        return "Message not found"
    problems = message.problems
    if not problems:
        return message.completion

    completion = message.completion.strip()

    prompt = f"message: {completion}\n\nproblems:\n"
    for p in problems:
        prompt += f"- {p}\n"
    prompt += "\ninstruction: Given the message and a list of problems identified in the message, please fix the message. Make as few changes as possible.\n\n"
    prompt += "revised message:"

    fixed_completion = wrapped_create_completion(
        model=OPENAI_COMPLETION_DAVINCI_3_MODEL,
        prompt=prompt,
        temperature=0,
        max_tokens=len(completion) + 10,
    )

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


def get_sequence_draft(
    value_props: list[str], client_sdr_id: int, archetype_id: int
) -> list[dict]:
    """Generates a sequence draft for a client.

    Args:
        value_props (List[str]): The value props to use in the sequence.
        client_sdr_id (int): The client SDR id.

    Returns:
        List[str]: The sequence draft.
    """
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    personalization_field_name = client.vessel_personalization_field_name

    # Prompt Engineering - Value Proposition
    prompt = f"Value Proposition:\n"
    for i, v in enumerate(value_props):
        prompt += f"{i+1}. {v}\n"

    # Prompt Engineering - Persona
    prompt += f"\nPersona:\n"
    prompt += f"- Name: {archetype.archetype}\n"
    prompt += f"- Description: {archetype.icp_matching_prompt}\n"
    prompt += f"- Fit Reason: {archetype.persona_fit_reason}\n"

    # Prompt Engineering - SDR
    prompt += f"\nSales Person:\n"
    prompt += f"- Name: {client_sdr.name}\n"

    # Prompt Engineering - Instructions
    prompt += f"\nInstructions:\n"
    prompt += (
        f"- Write a sequence of emails that targets the value props and persona.\n"
    )
    prompt += f"- The emails need to address the recipient using {{{{first_name}}}} as a placeholder for the first name.\n"
    prompt += f"- The emails need to build off of each other.\n"
    prompt += f"- The second email should open with a question.\n"
    prompt += f"- The third email should reference results or a case study.\n"
    prompt += f"- Limit the sequence to 3 emails.\n"
    prompt += f"- In only the first email, you must include {{{{{personalization_field_name}}}}} after the salutation but before the introduction and body.\n"
    prompt += f"- Do not include other custom fields in the completion.\n"
    prompt += f"- Sign the email using 'Best' and the Sales Person's name.\n"
    prompt += f"Example sequence:\n"
    prompt += f"subject: 80% of US Physicians are on Doximity\n"
    prompt += f"Hey {{First_Name}},"
    prompt += f"As Doximity’s official physician staffing firm, we use our exclusive access to 80% of U.S. physicians on Doximity and our sophisticated technology to intelligently source candidates so organizations like {{account_name_or_company}} can land their next physician hire faster and more cost-effectively."
    prompt += f"I’d love to chat for 15 minutes about how Curative can help fill your most challenging roles –⁠ when are you free to chat?"
    prompt += f"Thanks,"
    prompt += f"{{Your_Name}}"
    prompt += f"\n\n--\n\n"
    prompt += f"subject: Speciality market analysis report\n"
    prompt += f"Hey {{First_Name}},"
    prompt += f"Our exclusive access to Doximity allows us to have the deepest pool of active and passive candidates in the industry, using comprehensive data to identify where passive and active job seekers are for your search."
    prompt += f"I’d love to chat for 15 minutes about how Curative can help fill your most challenging roles –⁠ can you let me know what time works best for you?"
    prompt += f"Thanks,"
    prompt += f"{{Your_Name}}\n"
    prompt += f"\n\n--\n\n"
    prompt += f"subject: Sample of active/passive FM job seekers\n"
    prompt += f"Hey {{First_Name}},"
    prompt += f"Curative has access to a dynamic network of physicians that’s growing and being refreshed daily, allowing us to present new candidates not found on typical job boards."
    prompt += f"I’d love to set time aside to share the data we’re finding for physician placements at your org –⁠ when are you free to chat for 10 minutes? Would love to find a time!"
    prompt += f"Thanks,"
    prompt += f"{{Your_Name}}\n\n"

    # Prompt Engineering - Finish
    prompt += f"\nSequence:"

    # Generate Completion
    emails = wrapped_create_completion(
        # TODO: Use CURRENT_OPENAI_LATEST_GPT_MODEL when we gain access.
        model=OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
        prompt=prompt,
        temperature=0.7,
        frequency_penalty=1.15,
        max_tokens=600,
    )
    if not emails:
        return False

    # Parse Completion
    parsed_emails = []

    i = 0
    for email in re.split(r"\s+subject: ", emails, flags=re.IGNORECASE | re.MULTILINE):
        parts = email.strip().split("\n", 1)
        if len(parts) != 2:
            continue

        subject = re.sub(r"^subject: ", "", parts[0].strip(), flags=re.IGNORECASE)

        body = re.sub(r"--\s?$", "", parts[1].strip(), flags=re.IGNORECASE)
        body = re.sub(r"-\s?$", "", body, flags=re.IGNORECASE)
        if i == 0:
            body = re.sub(
                r"^(.+){{.+}},",
                lambda m: f"{m.group(1)}{{First_Name}},\n\n{{SellScale_Personalization}}",
                body,
            )

        parsed_emails.append(
            {
                "subject_line": subject.strip(),
                "email": body.strip(),
            }
        )
        i += 1

    return parsed_emails


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


# def post_icp_classification_prompt_change_request(
#     client_sdr_id: int, archetype_id: int, new_prompt: str
# ) -> tuple[bool, str]:
#     """Sends a message to Slack notifying SellScale of a requested ICP Classification Prompt change.

#     Args:
#         client_sdr_id (int): ID of the client SDR.
#         archetype_id (int): ID of the archetype.
#         new_prompt (str): The new prompt.

#     Returns:
#         bool: True if successful, False otherwise.
#     """
#     archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
#     if not archetype:
#         return False, "Archetype not found."

#     sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
#     if not sdr:
#         return False, "Client SDR not found."

#     return send_icp_classification_change_message(
#         sdr_name=sdr.name,
#         archetype=archetype.archetype, archetype_id=archetype.id, new_prompt=new_prompt
#     )


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
    archetype_id: int, prompt: str, send_slack_message: Optional[bool] = False, option_filters: Optional[dict] = None
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
                queue="ml_prospect_classification",
                routing_key="ml_prospect_classification",
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
                queue="ml_prospect_classification",
                routing_key="ml_prospect_classification",
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
        queue="ml_prospect_classification",
        routing_key="ml_prospect_classification",
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

        print(prompt)

        prompt += HARD_CODE_ICP_PROMPT

        # Generate Completion
        completion = wrapped_chat_gpt_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            model=OPENAI_CHAT_GPT_4_MODEL,
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
    response = wrapped_chat_gpt_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=int(len(initial_text) / 4) + 100,
    )
    return response


def ai_email_prompt(
    client_sdr_id: int,
    prospect_id: int,
    email_bump_framework_id: Optional[int] = None,
    overriden_blocks: Optional[list[str]] = None,
) -> str:
    """Generate an AI Email Prompt given a prospect. Uses the prospect's archetype and email bump framework (if given) to generate the prompt.

    If email_bump_framework_id is included, the email bump framework will be used to generate the prompt. Otherwise, the default SellScale blocks will be used.

    If overriden_blocks are included, the blocks will be used instead of the email bump framework or default SellScale blocks.

    Args:
        client_sdr_id (int): The client SDR ID
        prospect_id (int): The prospect ID
        email_bump_framework_id (Optional[int], optional): The email bump framework ID. Defaults to None.
        overriden_blocks (Optional[list[str]], optional): The blocks to override. Defaults to None.

    Returns:
        str: The AI Email Prompt

    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    account_research: list[AccountResearchPoints] = AccountResearchPoints.query.filter(
        AccountResearchPoints.prospect_id == prospect.id
    ).all()

    client_sdr_name = client_sdr.name
    client_sdr_title = client_sdr.title
    company_tagline = client.tagline
    company_description = client.description
    company_value_prop_key_points = client.value_prop_key_points
    company_tone_attributes = (
        ", ".join(client.tone_attributes) if client.tone_attributes else ""
    )

    persona_name = client_archetype.archetype
    persona_buy_reason = client_archetype.persona_fit_reason
    prospect_contact_objective = client_archetype.persona_contact_objective
    prospect_name = prospect.full_name
    prospect_title = prospect.title
    prospect_bio = prospect.linkedin_bio
    prospect_company_name = prospect.company

    prospect_research: list[
        ResearchPoints
    ] = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    research_points = ""
    for point in prospect_research:
        research_points += f"- {point.value}\n"

    account_points = ""
    for point in account_research:
        account_points += f"- {point.title}: {point.reason}\n"

    default_sellscale_structure = """
    1. Personalize the title to their company and or the prospect
    2. Include a greeting with Hi, Hello, or Hey with their first name
    3. Personalized 1-2 lines. Mentioned details about them, their role, their company, or other relevant pieces of information. Use personal details about them to be natural and personal.
    4. Mention what we do and offer and how it can help them based on their background, company, and key details.
    5. Use the objective for a call to action
    6. End with Best, (new line) (My Name) (new line) (Title)
"""

    block_structure = default_sellscale_structure

    # Initial Email
    if (
        client_archetype.email_blocks_configuration is not None
        and len(client_archetype.email_blocks_configuration) > 0
    ):
        block_structure = ""
        for index, block in enumerate(client_archetype.email_blocks_configuration):
            block_structure += f"{index + 1}. {block}\n"

    # Followup emails / test emails
    if email_bump_framework_id is not None:
        bf_email: BumpFrameworkEmail = BumpFrameworkEmail.query.get(
            email_bump_framework_id
        )
        block_structure = ""
        for index, block in enumerate(bf_email.email_blocks):
            block_structure += f"{index + 1}. {block}\n"

    if overriden_blocks is not None and len(overriden_blocks) > 0:
        block_structure = ""
        for index, block in enumerate(overriden_blocks):
            block_structure += f"{index + 1}. {block}\n"

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

Useful data:
{value_prop_key_points}

Tone: {company_tone}

Persona info:
Name: {persona_name}

Why they buy:
{persona_buy_reason}

Prospect info:
Prospect Name: {prospect_name}
Prospect Title: {prospect_title}
Prospect Bio:
"{prospect_bio}"
Prospect Company Name: {prospect_company_name}

More research:
{prospect_research}
{research_points}

Final instructions
- Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed".
- Use markdown as needed to accomplish the instructions.

Generate the subject line, one line break, then the email body. Do not include the word 'Subject:' or 'Email:' in the output.

I want to write this email with the following objective: {persona_contact_objective}

Output:""".format(
        structure=block_structure,
        client_sdr_name=client_sdr_name,
        client_sdr_title=client_sdr_title,
        company_tagline=company_tagline,
        company_description=company_description,
        value_prop_key_points=company_value_prop_key_points,
        company_tone=company_tone_attributes,
        persona_name=persona_name,
        persona_buy_reason=persona_buy_reason,
        prospect_name=prospect_name,
        prospect_title=prospect_title,
        prospect_bio=prospect_bio,
        prospect_company_name=prospect_company_name,
        prospect_research=account_points,
        research_points=research_points,
        persona_contact_objective=prospect_contact_objective,
    )

    return prompt


def generate_email(prompt: str) -> dict[str, str]:
    """Generate an email for a prospect.

    Args:
        prompt (str): The prompt to generate the email with

    Returns:
        dict[str, str]: The subject and body of the email
    """
    response = wrapped_chat_gpt_completion(
        [
            {"role": "system", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=400,
        model=OPENAI_CHAT_GPT_4_MODEL,
    )
    response = response if isinstance(response, str) else ""
    lines = response.split("\n")
    subject = lines[0].strip()
    subject = re.sub(r"^Subject:", "", subject, flags=re.IGNORECASE).strip()
    body = "\n".join(lines[1:]).strip()
    return {"subject": subject, "body": body}


def generate_followup_email_with_objective_prompt(
    client_sdr_id: int, prospect_id: int, thread_id: str, objective: Optional[str] = ""
) -> str:
    """Generate an email for a prospect.

    Args:
        client_sdr_id (int): The id of the client sdr
        prospect_id (int): The id of the prospect
        thread_id (str): The id of the thread
        objective (Optional[str]): The objective of the email. Defaults to None.

    Returns:
        string: The prompt for the email
    """
    from src.prospecting.nylas.services import get_email_messages_with_prospect
    from src.research.account_research import get_account_research_points_by_prospect_id

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    prospect: Prospect = Prospect.query.get(prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    research_points: ResearchPoints = ResearchPoints.get_research_points_by_prospect_id(
        prospect_id
    )
    research_points = [point.value for point in research_points]
    account_research = get_account_research_points_by_prospect_id(prospect_id)
    account_research = [
        point.get("title") + ": " + point.get("reason") for point in account_research
    ]
    objective = objective or archetype.persona_contact_objective

    # Convert past messages to text. Append '>' to each line to make it a quote
    past_messages = []
    past_messages_raw = get_email_messages_with_prospect(
        client_sdr_id, prospect_id, thread_id
    )
    if past_messages_raw:
        for thread in past_messages_raw:
            body: str = thread.get("body")
            bs = BeautifulSoup(body, "html.parser")
            body: str = bs.get_text()
            body: str = re.sub(r"\n+", "\n", body)
            body: str = "> " + body
            body: str = body.strip().replace("\n", "\n> ")
            past_messages.append(body)

    prompt = """Instructions: Write a follow up email to the previous email. The followup email is from the original sender. The followup email is trying to get the recipient's attention. The followup email should use information about the recipient in a highly personalized manner.

Email Tone: Casual and colloquial
Email Length: Medium (3-5 sentences)

Sender company information:
Name: {company_name}
Tagline: {company_tagline}
Description: {company_description}

Recipient research points:
-{research_points}

Recipient account research points:
-{account_research}

Outreach objective: {objective}

Past thread:
{past_threads}

Final instructions
- Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed"

Generate the subject line, one line break, then the email body. Do not include the word 'Subject:' or 'Email:' in the output.

Generated reply:""".format(
        company_name=client.company,
        company_tagline=client.tagline,
        company_description=client.description,
        research_points="\n-".join(research_points),
        account_research="\n-".join(account_research),
        objective=objective,
        past_threads="\n\n".join(past_messages),
    )

    return prompt


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

    response = wrapped_chat_gpt_completion(
        [{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
        model=OPENAI_CHAT_GPT_4_MODEL,
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

    response = wrapped_chat_gpt_completion(
        [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_tokens=10,
        model=OPENAI_CHAT_GPT_4_MODEL,
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
                "role": "user"
                if message.get("connection_degree") == "You"
                else "assistant",
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

    response = wrapped_chat_gpt_completion(
        messages,
        temperature=0.7,
        max_tokens=240,
        model="gpt-3.5-turbo-16k",
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

    response = wrapped_chat_gpt_completion(
        messages,
        temperature=0.7,
        max_tokens=240,
        model="gpt-3.5-turbo-16k",
    )

    match = re.search(r"\d+", response)
    if match:
        return int(match.group()) - 1
    else:
        return -1


@celery.task(bind=True, max_retries=3)
def test_rate_limiter(self, rate: str):
    from src.utils.slack import send_slack_message, URL_MAP

    send_slack_message(
        message=f"Testing rate_limiter at a rate of {rate}. Time:"
        + str(datetime.utcnow()),
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )
