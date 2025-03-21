from typing import Dict, List, Optional
from src.contacts.models import SavedApolloQuery
from src.email_outbound.models import ProspectEmailOutreachStatus
from src.ml.openai_wrappers import (
    DEFAULT_TEMPERATURE,
    OPENAI_CHAT_GPT_4_TURBO_MODEL,
    streamed_chat_completion_to_socket,
)
from src.li_conversation.models import LinkedInConvoMessage
from src.bump_framework.models import BumpFramework
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate

from src.research.models import IScraperPayloadCache
from app import db, celery
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect, ProspectStatus
from src.message_generation.models import (
    GeneratedMessage,
    GeneratedMessageEmailType,
    GeneratedMessageType,
)
from src.ml.models import (
    AIResearcherAnswer,
    AIResearcherQuestion,
    AIVoice,
    FewShot,
    TextGeneration, LLM,
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
from src.research.website.serp_helpers import search_google_news, search_google_news_raw
from src.utils.abstract.attr_utils import deep_get

import os

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")


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
    from src.prospecting.icp_score.services import (
        apply_icp_scoring_ruleset_filters_task,
    )

    if len(prospect_ids) > 0:
        # Run celery job for each prospect id
        apply_icp_scoring_ruleset_filters_task(
            client_archetype_id=archetype_id,
            prospect_ids=prospect_ids,
        )
    else:
        # Get all prospects for the client SDR id and archetype id
        prospects: list[Prospect] = Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.archetype_id == archetype_id,
        ).all()

        # Run celery job for each prospect
        apply_icp_scoring_ruleset_filters_task(
            client_archetype_id=archetype_id,
            prospect_ids=[prospect.id for prospect in prospects],
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

def chat_ai_verify_demo_set(
    messages: list[str], seller: str
) -> bool:
    """Verifies if the conversation is about setting a demo for a sale.
    Args:
        messages (list[str]): The conversation history.
        seller (str): The name of the seller.
        current_status (str): The current status of the conversation.
    Returns:
        bool: Whether the conversation is about a demo set.
    """
    # Construct the transcript
    transcript = ""
    for message in messages:
        transcript += message + "\n\n"

    prompt = """The following transcript was determined to feature a seller and a potential customer discussing a time to meet. 
    
    We would like to verify if they have agreed on the time to meet for a sales demonstration.
    Can you confirm, by replying either 0 (for False) or 1 (for True) that this conversation meets the following criteria for having a demo set?
    Criteria:
    The customer has agreed that they will be available at a time for some kind of meeting or sales demonstration.
    The customer has provided contact information, such as a phone number or email address.
    Note: Ensure that the scheduling is definitively confirmed. Be cautious, as participants might propose times and places without finalizing them.
    Verify that both parties have agreed on the specific time for their meeting, leaving no unresolved details.
    Consider nuanced language that might indicate a demo is set, such as phrases like "Looking forward to our conversation & potential collaboration," which could imply a confirmed meeting.
    If the conversation suggests that the customer is likely to attend the call, such as confirming a specific time works for them, then that will qualify as a demo set.
    Additionally, check for any follow-up actions or confirmations, like calendar invites or reminders, which further solidify the meeting.
    Be aware of edge cases where the customer might express interest but not commit to a specific time, or where the conversation includes tentative language that does not confirm a demo.
    If the customer has consented to be sent some kind of link or email to meet, this can also qualify as a demo set.
    Consider any other edge cases that might indicate a demo is set, such as the seller following up with a confirmation message that the customer acknowledges.

    One few shot example: 
    ['Sure! I will be out for a short while for\n
      Holiday can we connect next week ', 'That sounds good. Hope you enjoy!\n\nPS - 
      When are you back? I can reach back out then.', 'Thanks so much the week of the 15th would be great.
        Appreciate you look forward to connecting \n\nJen ']

    Important: ONLY respond with a 0 (for False) or 1 (for True). Ensure that you are 100% certain that the demo was scheduled.
    
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
        model='gpt-4o',
        type="MISC_CLASSIFY",
    )

    match = re.search(r"\d+", response)
    if match:
        number = int(match.group(0))
    else:
        return False

    return number == 1


def chat_ai_verify_scheduling_convo(
    messages: list[str], seller: str, current_status: ProspectStatus
) -> bool:
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

Criteria:
The two parties are showing a willingness to schedule a meeting.
Note: The scheduling must be unresolved to be true-- be careful. people might be suggesting times and places that work without having confirmed.
Make sure that both parties have not settled on when and where they will be seeing each other, and that there are hanging questions.

If the CURRENT_STATUS is DEMO_SET, please automatically return 0.

Seller: {seller_name}
CURRENT_STATUS: {current_status}

--- Start Transcript ---
{transcript}
--- End Transcript ---

""".format(
        seller_name=seller, transcript=transcript, current_status=current_status.value
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
    stream_event: Optional[str] = None,
    stream_room_id: Optional[str] = None,
) -> Optional[str]:
    # type = "LI_MSG_INIT" | "LI_MSG_OTHER" | "RESEARCH" | "EMAIL" | "VOICE_MSG" | "ICP_CLASSIFY"
    # | "TEXT_EDITOR" | "MISC_CLASSIFY" | "MISC_SUMMARIZE" | "LI_CTA" | "CLIENT_ASSETS" | "SEQUENCE_GEN_<ID>"

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

    # Handle streaming
    if stream_event:
        if json_msgs and text_gen:
            from src.sockets.services import send_socket_message

            send_socket_message(
                stream_event,
                {"response_delta": text_gen.completion, "extra_data": None},
                room_id=stream_room_id,
            )
            return text_gen.completion
        else:
            completion = streamed_chat_completion_to_socket(
                event=stream_event,
                room_id=stream_room_id,
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return completion

    # Handle normal completion
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


def get_perplexity_research(prospect_id: int, client_sdr_id: int) -> str:
    prospect: Prospect = Prospect.query.get(prospect_id)

    if prospect.client_sdr_id != client_sdr_id:
        return "Error: Prospect does not belong to the client SDR."

    full_name = prospect.full_name
    title = prospect.title
    company = prospect.company
    linkedin_url = prospect.linkedin_url

    messages = [
        {
            "role": "system",
            "content": "You are an AI researcher that will give me correct and factual information based on the linkedin link provided.",
        },
        {
            "role": "user",
            "content": "Tell me more about {full_name}, who is a {title} at {company}. Here is the linkedin link: {linkedin_url} but please look at various other sources on the internet for information about them as well".format(
                full_name=full_name,
                title=title,
                company=company,
                linkedin_url=linkedin_url,
            ),
        },
    ]

    response = get_perplexity_response("llama-3-sonar-large-32k-online", messages)
    return response["content"]


def get_perplexity_response(model: str, messages: list) -> dict:
    import requests
    import json

    url = "https://api.perplexity.ai/chat/completions"
    payload = {"model": model, "messages": messages, "return_citations": True, "return_images": True}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": "Bearer " + PERPLEXITY_API_KEY,
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response.text)
    x = json.loads(response.text)
    result = {
        "content": x["choices"][0]["message"]["content"],
        "citations": x.get("citations", []),
        "images": x.get("images", [])
    }

    return result


def simple_perplexity_response(model: str, prompt: str):
    """
    Creates a basic set of messages and sends them to the perplexity API to get a response
    """
    messages = [{"role": "user", "content": prompt}]

    response = get_perplexity_response(model, messages)
    return response["content"], response["citations"], response["images"]


def answer_question_about_prospect(
    client_sdr_id: int, prospect_id: int, question: str, how_its_relevant: str, room_id: str, questionType: str
):
    from src.sockets.services import send_socket_message
    """
    Answer a question about a prospect based on the question number
    """
    prospect: Prospect = Prospect.query.get(prospect_id)

    prospect_str = prospect.full_name + (
        " (" + prospect.title + " @ " + prospect.company + ")"
    )
    company_str = prospect.company
    if prospect.company_url:
        company_str += " (" + prospect.company_url + ")"

    prompt = question.replace("[[prospect]]", prospect_str).replace(
        "[[company]]", company_str
    )

    print("\n### RUNNING PERPLEXITY ###")

    print("Step 1: Answering question")
    print(prompt)

    response, response_citations, response_images = simple_perplexity_response("llama-3-sonar-large-32k-online", prompt)
    print("\nStep 2: Raw response")
    print(response)

    validate_with_gpt = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": "You are an AI verifier. I am going to provide a response to a question about a prospect and a 'how it works'. I need you to respond with a JSON with two items: \nis_yes_response (bool) a simple true or false if the response is a positive response or not. 'No' responses are false, 'Yes' responses are true, and 'Unknown' responses are false too.\ncleaned_research(str) take the response and only return the most relevant pieces of information. Do as minimal editing as possible to the result.\nrelevancy_explanation (str): A simple sentence that should indicate if the research is relevant or nor irrelevant, with a short 1 sentence justification why.",
            },
            {
                "role": "user",
                "content": f"Here is the response to the question: {response}\n\nHow it's relevant: {how_its_relevant}\noutput:",
            },
        ],
        model="gpt-4o",
        max_tokens=400,
    )
    validate_with_gpt = json.loads(
        validate_with_gpt.replace("json", "").replace("`", "")
    )
    print("\nStep 3: Validating response")
    print(validate_with_gpt)

    if room_id:
        formatted_data = {
            "title": question,
            "type": questionType,
            "content": validate_with_gpt.get("cleaned_research"),
            "raw_response": response,
            "ai_response": validate_with_gpt.get("relevancy_explanation"),
            "status": validate_with_gpt.get("is_yes_response"),
            "room_id": room_id,
            "citations": response_citations,
            "images": response_images
        }
        send_socket_message('stream-answers', formatted_data, room_id)

    return True, response, validate_with_gpt, response_citations, response_images

def get_template_suggestions(archetype_id: int, template_content: str ):
    '''
    get template suggestions from open ai, not perplexity based on the content of the template
    and the archetype itself
    '''
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    client: Client = Client.query.get(archetype.client_id)
    client_description = client.description
    company_name = client.company
    

    import json

    def get_validated_response(messages, model, max_tokens, retries=3):
        for attempt in range(retries):
            response = wrapped_chat_gpt_completion(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
            )
            try:
                return json.loads(response.replace("json", "").replace("`", ""))
            except json.JSONDecodeError:
                if attempt == retries - 1:
                    raise
        return None

    messages = [
        {
            "role": "system",
            "content": ''' 
            You are an email assistant that will help me write smart and effective email
            templates for a sales email. The company sending an email is called {company_name}. 
             {company_name} is {client_description}. 
               You will come up with a few different styles of email templates

            Style: Brevity-based
            Descriptioin: just be shorter - no one has time to read.

            Style: Offer-based
            Description: Provide a unique out of this world offer

            Style: Pain-based
            Description: write a narrative extremely emotionally about a problem

            Please return the style as at least the first three (pain, shorter, offer). You can provide 2 other wildcards.
            Go!
            '''.format(company_name=company_name, client_description=client_description),
        },
        {
            "role": "user",
            "content": '''Here is the template: {template_content}\n\n Please know I am reaching out to {archetype_description}. Please responsd to me only and nothing else but a array of JSONs response, where
            each object in the array will have a style string and content string. Format it with tabs and newlines as necessary. Put placeholders in double brackets like [[Customer Name]] or others. Encourage more use of placeholders. 
            Match the style of the template as closely as possible while conforming to the style.
            '''.format(template_content=template_content, archetype_description=archetype.archetype),
        },
    ]

    validate_with_gpt = get_validated_response(messages, "gpt-4o", 600)

    return validate_with_gpt

def add_few_shot(client_archetype_id, original_string, edited_string, prospect_id=None, template_id = None):
    """
    Add a new FewShot entry using the provided parameters.

    Args:
        client_archetype_id (int): The ID of the client archetype.
        original_string (str): The original string before any edits.
        edited_string (str): The string after edits have been made.
        prospect_id (int, optional): The ID of the prospect. Default is None.

    Returns:
        bool: True if the entry was added successfully, False otherwise.
    """
    try:
        client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

        client_sdr: ClientSDR = ClientSDR.query.get(client_archetype.client_sdr_id)

        client: Client = Client.query.get(client_sdr.client_id)
        
        if prospect_id:


            if (template_id):
                # Get the template
                template: EmailSequenceStep = EmailSequenceStep.query.get(template_id)
                template_string = template.template
                
            print('prospect_id', prospect_id)
            prospect: Prospect = Prospect.query.get(prospect_id)

            ai_researcher_answers: list[AIResearcherAnswer] = AIResearcherAnswer.query.filter_by(prospect_id=prospect_id).all()

            # Collect research information
            research_points = '\n'.join([
                f"- #{index + 1}: {AIResearcherQuestion.query.get(answer.question_id).key}\n\t- {answer.short_summary}\n\t- {answer.relevancy_explanation}"
                for index, answer in enumerate(ai_researcher_answers) if answer.is_yes_response
            ])
            # Precede the edited_string with cursory information about the prospect and research
            cursory_info = (
                f"Recipient Information:\n"
                f"Prospect Name: {prospect.full_name}\n"
                f"Prospect Title: {prospect.title}\n"
                f"Prospect Company: {prospect.company}\n\n"
                f"Sender Information:\n"
                f"My Name: {client_sdr.name}\n"
                f"My Title: {client_sdr.title}\n"
                f"My Company: {client.company}\n\n"
                f"Template:\n{template_string}\n\n"
                f"Research points:\n{research_points}\n\n"
                f"Generated Email:\n{'#' * 10}\n{edited_string}"
            )
            edited_string = cursory_info

        # Create a new FewShot entry
        new_few_shot = FewShot(
            original_string=original_string,
            edited_string=edited_string,
            nuance='',
            ai_voice_id=client_archetype.ai_voice_id
        )
        db.session.add(new_few_shot)
        db.session.commit()
        return new_few_shot.to_dict()
    except Exception as e:
        print(f"Error adding FewShot entry: {e}")
        db.session.rollback()
        return False
def get_nice_answer(userInput, client_sdr_id=None, campaign_id=None, context_info=None):
    """
    Get like a nice answer or something from the AI
    """

    userInfo = "here is some contextual information about the DOM. Please know that this information surrounds what the user is attempting to input text into. They are using your help to get a good answer" + context_info + ". If I gave you a conversation there, do not write any placeholder data."
    userInput = userInfo + " ok, finally: here is the user input: " + userInput + '\n \n ok, there is the user input. Only give the answer to the input, do not prefix it with anything. Do not give the answer like its repeating what the user asked. If the user appears to be stating something please state what they said more eloquently given the context. Be careful, sometimes the system might have too much context, so you need to abide by ONLY what the user is asking for. i.e. if they asked for a template only give them the template.'

    system_prompt = '''You are an AI for an automated outbound software called sellscale will generate do exactly what the user's request is to their hearts content. 
            If you are asked to write any placeholder data, please surround it with two square brackets like: '[[',  and ']]' If the user is asking for an email, they mean the body, not the subject and body. Only do as they say. Again, do not premise the answer to the user.
            '''
    if (client_sdr_id):
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client : Client = client_sdr.client
        system_prompt += '''
        The user's company is called {client_name} and the user's name is {sdr_name}.
        '''.format(client_name=client.company, sdr_name=client_sdr.name)
        if (client_sdr.title):
            system_prompt += '''
            The user's title is {sdr_title}
            '''.format(sdr_title=client_sdr.title)

    if (campaign_id):
        campaign: ClientArchetype = ClientArchetype.query.get(campaign_id)
        system_prompt += '''
        The campaign is called {campaign_name}
        '''.format(campaign_name=campaign.archetype)

    system_prompt += 'please be as brief as possible. Only give the answer to the input, do not prefix it with anything. Do not give the answer like its repeating what the user asked and do not premise the answer.'

    messages = [
        {
            "role": "user",
            "content": f"{system_prompt}\n{userInput}"
        }
    ]
    response = wrapped_chat_gpt_completion(
        messages=messages,
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000
    )
    return response
def get_few_shots(ai_voice_id):
    """
    Get all FewShot entries for a given AI voice.
    Args:
        ai_voice_id (int): The ID of the AI voice.

    Returns:
        list: A list of FewShot entries.
    """
    try:
        few_shots: list[dict] = [few_shot.to_dict() for few_shot in FewShot.query.filter_by(ai_voice_id=ai_voice_id).all()]
    except Exception as e:
        return []
    return few_shots

def get_all_ai_voices(client_sdr_id):
    """
    Get all the AI voices available
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    voices: list[AIVoice] = AIVoice.query.filter_by(client_id=client_sdr.client_id).all()
    if not voices:
        return []
    return [voice.to_dict() for voice in voices]

def create_ai_voice(name: str, client_sdr_id: int, client_archetype_id: int):
    """
    Create a new AI voice
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        raise ValueError(f"ClientSDR with id {client_sdr_id} not found")

    new_voice: AIVoice = AIVoice(name=name, client_sdr_created_by=client_sdr.id, client_id=client_sdr.client_id)
    db.session.add(new_voice)
    db.session.flush()  # Ensure new_voice.id is available

    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not client_archetype:
        raise ValueError(f"ClientArchetype with id {client_archetype_id} not found")

    client_archetype.ai_voice_id = new_voice.id
    db.session.add(client_archetype)
    db.session.commit()
    return new_voice.to_dict()

def assign_ai_voice(voice_id: int, archetype_id: int):
    """
    Assign an AI voice to an archetype. If voice_id is None, set the archetype's voice id to null.
    """
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if voice_id is None:
        archetype.ai_voice_id = None
    else:
        voice: AIVoice = AIVoice.query.get(voice_id)
        archetype.ai_voice_id = voice.id
    db.session.add(archetype)
    db.session.commit()
    return archetype.to_dict()

def update_few_shot(id: int):
    """
    Delete a FewShot entry.

    Args:
        id (int): The ID of the FewShot entry.

    Returns:
        bool: True if the deletion was successful, False otherwise.
    """
    few_shot: FewShot = FewShot.query.get(id)
    if not few_shot:
        return False
    db.session.delete(few_shot)
    db.session.commit()
    return True
@celery.task
def one_shot_sequence_generation(
    client_sdr_id: int,
    campaign_id: int,
    purpose: str,
    sequence_type: str = 'LINKEDIN-TEMPLATE',
    num_steps: Optional[int] = 2,
    num_variants: Optional[int] = 1,
    company_name: Optional[str] = "",
    persona: Optional[str] = "",
    with_data: Optional[str] = "",
):
    prompt = """You are a sequence generator. I will provide you with a company, company context, campaign name, and a little bit of information about the 'purpose of the campaign', and you will generate an incredible sequence that will get me conversations.
    You will be given this number of steps: {num_steps} and this number of variants: {num_variants}.
    There can be a number of variants that you can generate. be sure to vary your angles, message, and length for each variant. The style and length of the message should be different for each variant. If one variant's message is long, the next variant at the same step should be shorter.
    Here are a couple top examples:
    -------------------
    EXAMPLE 1:
    Company: NewtonX
    Company Description: NewtonX is the only B2B market research company that connects decision makers with verified expert insights they can trust. We are doing quantitative and qualitative research leveraging our AI-powered recruitment technology that has the highest scale, quality, and accuracy in the market. Many leading clients like Salesforce or Microsoft have done large scale A/B tests between our data and competitor data which showed that their fraud rates are >30% while ours are <1% across the board. We empower business decision makers to make product, brand, go-to-market, M&A and investment decisions in confide. 
    Campaign Name: PTAL - Paid Interview - $150 - New PTAL List 6/14 - Group 1
    Purpose: We are contacting prospects with the intention of offering them $150 gift cards for 30 minutes of their time to conduct a B2b business research interview.

    Generated Sequence:
    Step 1 (Variant 1):
    - Angle: Great to connect
    - Text: Hi [[first_name]], would you be open to a 30 min interview for $150? We're interviewing brand marketing professionals like yourself about survey data quality on their B2B studies for brand. Happy to also share the findings with you once we finish the report. Look forward to connecting. Thanks!

    Step 2 (Variant 1): 
    - Angle: Follow Up 1
    - Text: Hi [[first_name]].

    I wanted to provide a bit more context on the interview - we’re interested in hearing about your experiences regarding B2B market research data across a variety of methodologies and provider types. All responses will be confidential and anonymized for a thought leadership report on the state of B2B market research data quality that we’re publishing, for which you’ll get exclusive early access. We recently published thought leadership together with our partners at Interbrand, Wall Street Journal, Google, and McKinsey if you want to take a look at previous examples: https://www.newtonx.com/resources/


    Given your role, we think your perspective would be very valuable and would love to chat. Let us know if that works on your end.

    Step 3 (Variant 1): 
    - Angle: Follow Up 2
    - Text: Hey [[first name]] - here's a thought leadership report we recently helped Google release about Gen AI in retail: https://www.googlecloudpresscorner.com/2024-01-11-Google-Cloud-Shares-New-Research-on-2024-Outlook-on-Generative-AI-in-Retail

    We're really excited about our B2B data quality study and would love to include your perpsective.I'm happy to connect at your convenience. What works best for you?

    -------------------------

    EXAMPLE 2:
    Company: Reacher
    Company Description: Reacher works 24/7 to send thousands of messages to TikTok Shop Affiliates, earning you hundreds of sample requests for your products every day.
    Campaign Name: rows 1-351 of 5K results fastmoss sheet
    Purpose: We are contacting heads of affiliate marketing and growth to see if they'd be interested in our automated outbound system for TikTok outreach.

    Generated Sequence:
    Step 1 (Variant 1): 
    - Angle: Simple Connect
    - Text: Hi [[first name]]! I noticed you work as a [[lowercase role]] at [[company]] I built a tool that helps brands use TikTok Shop's affiliate program. I'd love your feedback on our solution!
    
    Step 1 (Variant 2):
    - Angle: Hook
    - Text: Do you want to easily be a part of TikTok's affiliate program? I have a solution that can help you get started. I'd love to chat with you about it!

    Step 2 (Variant 1): 
    - Angle: Intro
    - Text: For some context I developed an affiliate marketing solution for TikTok Shop as a side project and I am looking for people to try it out and give feedback on it's usefulness!

    I HATE when people waste my time so I won't waste yours. Given your role at [[informalized company name]] I promise there is at LEAST a 1% chance you will find this useful.

    The solution does the following for your Brand on TTS:
    1. Send ~1,000 messages or target collaborations to creators per day
    2. Automated Follow up messages
    3. Management Portal for you to control the software
    4. Upcoming AI-enhanced CRM for TTS creator management
    5. Exclusive database of 600K+ creators + a portion of their emails

    Are you interested in trying it out for free? Worst that can happen is that you get 3 days of free affiliate outreach for your store!

    If you get this far and still don't want to try it, please do me a solid and treat me like a human just trying to make a living and at least tell me no rather than ghost me. I appreciate it! Thanks!
    
    Step 2 (Variant 2):
    - Angle: Exclusive Offer
    - Text: For some context, I will be giving you exclusive trial to our affiliate marketing solution for TikTok Shop. I am looking for people to try it out and give feedback on it's usefulness!
    ----------------------------

    EXAMPLE 3: 
    Company: Curative
    Company Description: Curative is the healthcare staffing firm of Doximity, the largest community of medical professionals in the country, with 80% of physicians and 50% of nurse practitioners and physician assistants. We leverage data, technology, and deep industry expertise to intelligently source high-quality physician and advanced practitioner candidates.
    Campaign Name: Leaders at FQHC
    Purpose: We want to reach out to leaders at FQHC hospitals to see if they are hiring for any roles and see if they'd be interested in partnering with us to get those roles filled.

    Generated Sequence:
    Step 1 (Variant 1):
    - Angle: Simple Nice Greeting
    - Text: Hi [[first name]]! I've enjoyed following your journey to [[informalized company name]] as the [[lowercase title]]. I work with providers who are passionate about working with underserved populations. I'd love to chat and share more about it if you're open to learning more.

    Step 2 (Variant 1): 
    - Angle: Do you have any challenges or priorities?
    - Text: Hi [[first name]],
    Thank you for accepting my connection request. As an [[lowercase title name]] I'm sure you must encounter unique challenges when it comes to recruiting physicians and streamlining that workflow. I'd be happy to share some insights on how we at Curative have helped similar roles and facilities enhance their physician recruitment process.
    It would be great to learn from your experiences and discuss how we can potentially help lighten your load.
    Would you be open to having a chat about this?
    Best,
    [[my name]]

    Step 3 (Variant 1): 
    - Angle: Coffee chat?
    - Text: Hi [[prospect name]]!  I know you're super busy. If possible, I'd love to chat with you. Coffee is on me. Would you be too busy for a 10 min call this week?

    --------------------

    Now your turn. Make a sequence with these details:

    EXAMPLE 4:
    Company: {company}
    Company Description: {company_description}
    Campaign Name: {campaign_name}
    Purpose: {purpose}

    NOTE: The first message or step should be less than 300 characters.
    NOTE: You are to create {num_steps} steps in the sequence. Each sequence should have {num_variants} variants. The variants should be different from each other but still follow the same style.
    NOTE: Follow the style of the examples provided above. Be human, creative, and engaging.
    NOTE: In general, keep the messages not too verbose. Goal on 1-2 sentences range per message.
    NOTE: Only respond with the sequence and nothing else.
    NOTE: You might be given some assets, like websites or additional information or material to be used as part of your messaging. Include those in your messages.

    Generated Sequence:"""

    try:

        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)
        client_archetype: ClientArchetype = ClientArchetype.query.get(campaign_id)

        # Set the sequence generation in progress flag to True
        client_archetype.li_seq_generation_in_progress = True
        db.session.add(client_archetype)
        db.session.commit()

        company = client.company
        company_description = client.description
        campaign_name = client_archetype.archetype
        purpose = purpose

        enriched_prompt = prompt.format(
            company=company,
            company_description=company_description,
            campaign_name=campaign_name,
            purpose=purpose,
            num_steps=num_steps,
            num_variants=num_variants,
        )
        context_info = f'''
            Company: {company}
            Company Description: {company_description}
            Campaign Name: {campaign_name}
            '''

        ctas = []

        if sequence_type == 'LINKEDIN-TEMPLATE':
            response = wrapped_chat_gpt_completion(
                messages=[
                    {
                        "role": "user",
                        "content": enriched_prompt
                    }
                ],
                model='claude-3-opus-20240229',
                max_tokens=3000
            )
        elif sequence_type == 'LINKEDIN-CTA':
            from src.personas.services_generation import generate_linkedin_cta
            print('linkedin cta')
            response = wrapped_chat_gpt_completion(
                messages=[
                    {
                        "role": "user",
                        "content": enriched_prompt
                    }
                ],
                model='claude-3-opus-20240229',
                max_tokens=3000
            )

            from src.message_generation.services import generate_cta_examples
            ctas = generate_cta_examples(company_name, persona, with_data)
        else:
            from src.personas.services_generation import generate_email_follow_up_quick_and_dirty, generate_email_initial
            response = generate_email_initial(3, client_archetype.client_id, campaign_id, context_info, '', purpose, None, None, num_steps=num_steps, num_variants=num_variants)
            # response = response + '\n + \n + here are some followup emails:' + generate_email_follow_up_quick_and_dirty(3, client_archetype.client_id, campaign_id, 1, context_info, '', purpose, None, None)

        if sequence_type == 'LINKEDIN-TEMPLATE':
            prompt = """You are a JSON converter. I will provide you with a sequence of messages, and you will convert it into a JSON object with an array of objects with a 'assets', 'step_num', 'angle', and 'text' key for each entry.

            ex. {{ "messages": [ {{"assets": [], "step_num": 0, "angle": "Title 1", "text": "Message 1"}}, {{"assets": [], "step_num": 1, "angle": "Title 2", "text": "Message 2"}} ] }}

            Here is the sequence:
            {response}

            NOTE: Only respond with the JSON object and nothing else.
            NOTE: There can be multiple elements with the same "step_num" if you are generating multiple variants per step.
            
            JSON Output:""".format(response=response)
        
        elif sequence_type == 'EMAIL':
            prompt = """You are a JSON converter. I will provide you with a sequence of messages, and you will convert it into a JSON object with an array of objects with 'subject_lines' and 'steps' keys.

            ex. {{"subject_lines": [{{"text": "Subject Line 1"}}, {{"text": "Subject Line 2"}}], "steps": [{{"assets": [], "step_num": 1, "angle": "Title 1", "text": "Message 1\nwith multiple lines"}}, 
            {{"assets": [], "step_num": 2, "angle": "Title 2", "text": "Message 2"}}, {{"assets": [], "step_num": 3, "angle": "Title 3", "text": "Message 3"}}]}}

            Here is the sequence:
            {response}

            NOTE: Only respond with the JSON object and nothing else. Please generate some followups in the empty steps as well.
            NOTE: There can be multiple elements with the same "step_num" if you are generating multiple variants per step.
            
            JSON Output:""".format(response=response)

        elif sequence_type == 'LINKEDIN-CTA':
            prompt = """You are a JSON converter. I will provide you with a sequence of messages, and you will convert it into a JSON object with an array of objects with 'messages' as the key containing an array of objects with 'assets', 'step_num', and 'text' keys for each entry.

            ex. {{"messages": [{{"assets": [], "step_num": 1, "angle": "Title 1", "text": "Bump Message 1"}}, {{"assets": [], "step_num": 2, "angle": "Title 2", "text": "Bump Message 2"}}]}}
            
            Here is the sequence:
            {response}

            NOTE: Only respond with the JSON object and nothing else.
            NOTE: There can be multiple elements with the same "step_num" if you are generating multiple variants per step.
            
            JSON Output:""".format(response=response)

        elif sequence_type.startswith('LINKEDIN-'):
            prompt = """You are a JSON converter. I will provide you with a sequence of messages, and you will convert it into a JSON object with an array of objects with 'steps' as the key containing an array of objects with 'title', 'step_num', 'assets', 'angle', and 'text' keys for each entry.

            ex. {{"steps": [{{"step_num": 2, "angle": "Title 1", "text": "Bump Message 1"}}, {{"step_num": 3, "angle": "Title 2", "text": "Bump Message 2"}}]}}

            Here is the sequence:
            {response}

            NOTE: Only respond with the JSON object and nothing else.
            
            JSON Output:""".format(response=response)

        response = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model='gpt-4o',
            max_tokens=3000
        )

        sanitized_response = response.replace("json", "").replace("`", "")

        json_data = json.loads(sanitized_response)

        final = []

        for cta in ctas:
            text = cta['cta']
            type = cta['tag'].replace("[", "").replace(" ", "") + "-Based"

            final.append({"text": text, "type": type})

        cta_json_data = {"ctas": final}

        from src.personas.services_creation import add_sequence

        add_sequence(
            client_id=client.id,
            archetype_id=client_archetype.id,
            sequence_type=sequence_type,
            subject_lines=json_data.get("subject_lines") if sequence_type == 'EMAIL' else [],
            steps=json_data.get("steps") if sequence_type == 'EMAIL' else json_data.get("messages"),
            override=False,
            new_ctas=cta_json_data.get("ctas") if sequence_type == 'LINKEDIN-CTA' else [],
        )
        # except Exception as e:
        #     print(f"Error generating sequence: {e}")

        # Set the sequence generation in progress flag to False

    except Exception as e:
        import traceback
        print(f"Error generating sequence: {e}")
        print("Stack trace:", traceback.format_exc())

    if sequence_type.startswith('LINKEDIN-') or sequence_type == 'LINKEDIN-CTA':
        client_archetype.li_seq_generation_in_progress = False
    else:
        client_archetype.email_seq_generation_in_progress = False
    db.session.add(client_archetype)
    db.session.commit()
    try: 
        return json_data
    except:
        return ''

@celery.task
def find_contacts_from_serp(
    archetype_id: int,
    purpose: str
):
    query ="""
You are a converter. Convert the purpose into a search.

Examples:
Input: I want to find doctors who work at the top 50 hospitals so I can give them an AI tool to unlock more value from the top CPT codes right now
Output: "site:linkedin.com/in/ doctor at top 50 hospital owners"

Input: Startup founders who recently raised a Series B in the last 4 months. I want to target them for a partnership so I can feature them in our upcoming blog post.
Output: "site:linkedin.com/in/ startup founder raised Series B in the last 4 months"

NOTE: Only respond with the search query and nothing else.

Input: {}
Output:"""

    query = query.format(purpose)
    output = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": query
            }
        ],
        model='gpt-4o',
        max_tokens=200
    )

    search_results = search_google_news_raw(
        output.replace('"', '')
    )

    links = [x['link'] for x in search_results['organic_results']]

    from src.prospecting.services import create_prospect_from_linkedin_link
    for link in links:
        create_prospect_from_linkedin_link.delay(
            archetype_id=archetype_id,
            url=link
        )

    return links


def generate_strategy_copilot_response(chat_content: List[Dict[str, str]], client_sdr_id: Optional[int] = None):
    """
    Generate a response for the Strategy Copilot based on the chat content.
    We will grab our user prompt from the llm table and have that be our initial prompt.
    :param chat_content: a list of dictionaries that contain the chat content
    the keys will be:
    sender: "assistant" or "user"
    query: <the message>
    id: <message_id>
    :return: {"response": response}
    """

     #look at icps for client, based on chat content, infer which ICP is being talked about and 
    all_icps_in_client: list[SavedApolloQuery] = []
    if client_sdr_id:
        print(f"Fetching ClientSDR with ID: {client_sdr_id}")
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        print(f"ClientSDR fetched: {client_sdr}")
        all_icps_in_client = SavedApolloQuery.query.join(ClientSDR, SavedApolloQuery.client_sdr_id == ClientSDR.id)\
            .filter(ClientSDR.client_id == client_sdr.client_id, SavedApolloQuery.is_prefilter == True).all()
        print(f"All ICPs in client: {all_icps_in_client}")
        
    icp_addition_string = ''
        
    if all_icps_in_client:
        icp_prompt_string = "Here are the ICPs for this client: \n"
        for icp in all_icps_in_client:
            icp_prompt_string += f"ICP: {icp.custom_name}, segment description: {icp.segment_description}, value proposition: {icp.value_proposition}\n"
        print(f"ICP Prompt String: {icp_prompt_string}")
        
        # Include chat content into the ICP question
        chat_content_string = "\n".join([f"{chat['sender']}: {chat['query']}" for chat in chat_content])
        icp_prompt_string += f"\nChat Content:\n{chat_content_string}\nWhich ICP is being talked about in this conversation and what are the titles included here?"
        print(f"ICP Prompt String with Chat Content: {icp_prompt_string}")

        response_schema = {
        "name": "icp_determination",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "icp_title": {"type": "string"},
                "included_titles": {"type": "string"},
                },
                "required": ["icp_title", "included_titles"],
                "additionalProperties": False
            }
        }

        print("Sending prompt to GPT model...")
        response = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": icp_prompt_string
                }
            ],
            model="gpt-4o-2024-08-06",
            max_tokens=300,
            response_format={"type": "json_schema", "json_schema": response_schema}
        )
        print(f"Response from GPT model: {response}")

        response = json.loads(response)
        icp_title = response.get("icp_title")
        included_titles = response.get("included_titles")
        print(f"ICP Title: {icp_title}, Included Titles: {included_titles}")

        icp_addition_string = f"\n\nIn the result, also, explicitly include copy like 'ICP to match' : \"{icp_title}\"\" and \"Included Titles: {included_titles}\n\n"

    # Grabbing initial user prompt from database
    llm = LLM.query.filter_by(name='strategies_copilot').first()
    initial_prompt = llm.user
    model = llm.model
    max_tokens = llm.max_tokens

    chat_log = [{"role": "user", "content": initial_prompt + icp_addition_string}]

    # print('params are', chat_content, prompt, current_csv)
    # Ensure chat_content is a list of dictionaries
    if isinstance(chat_content, str):
        chat_content = eval(chat_content)

    for index in range(len(chat_content)):
        chat = chat_content[index]

        if index == len(chat_content) - 1:
            chat_log.append({"role": chat.get("sender"), "content": f"User's last message: {chat.get('query')}"})
            break
        else:
            chat_log.append({"role": chat.get("sender"), "content": chat.get("query")})

    chat_gpt_response = wrapped_chat_gpt_completion(
        model=model,
        messages=chat_log,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=max_tokens
    )

    response = chat_gpt_response.strip()

    return {"response": response}

