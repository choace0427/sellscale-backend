from datetime import datetime
from typing import List
from app import db, celery
import os
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
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
    CURRENT_OPENAI_DAVINCI_MODEL,
    CURRENT_OPENAI_CHAT_GPT_MODEL,
)
import regex as rx
import re
import math
import openai
import json


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

    print(prompt)
    fixed_completion = wrapped_create_completion(
        model=CURRENT_OPENAI_DAVINCI_MODEL,
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
        model=CURRENT_OPENAI_DAVINCI_MODEL,
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
    prompt += f"- Description: {archetype.persona_description}\n"
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
        model=CURRENT_OPENAI_CHAT_GPT_MODEL,
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
        str: The prompt.
    """
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return None

    return archetype.icp_matching_prompt


def post_icp_classification_prompt_change_request(
    client_sdr_id: int, archetype_id: int, new_prompt: str
) -> tuple[bool, str]:
    """Sends a message to Slack notifying SellScale of a requested ICP Classification Prompt change.

    Args:
        client_sdr_id (int): ID of the client SDR.
        archetype_id (int): ID of the archetype.
        new_prompt (str): The new prompt.

    Returns:
        bool: True if successful, False otherwise.
    """
    from src.automation.slack_notification import send_slack_message, URL_MAP

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return False, "Archetype not found."

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False, "Client SDR not found."

    message_sent = send_slack_message(
        message="ICP Classification Prompt Change Requested",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Pulse Check Change Requested - {sdr}".format(sdr=sdr.name),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Persona: {persona} ({archetype_id})".format(
                            persona=archetype.archetype, archetype_id=archetype_id
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


def patch_icp_classification_prompt(archetype_id: int, prompt: str) -> bool:
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

    archetype.icp_matching_prompt = prompt

    db.session.add(archetype)
    db.session.commit()

    return True


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
        for prospect_id in prospect_ids:
            icp_classify.apply_async(
                args=[prospect_id, client_sdr_id, archetype_id],
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
        for prospect in prospects:
            icp_classify.apply_async(
                args=[prospect_id, client_sdr_id, archetype_id],
                queue="ml_prospect_classification",
                routing_key="ml_prospect_classification",
                priority=1,
            )

    return True


@celery.task(bind=True, max_retries=2)
def icp_classify(self, prospect_id: int, client_sdr_id: int, archetype_id: int) -> bool:
    """Classifies a prospect as an ICP or not.

    Args:
        prospect_id (int): The prospect id.
        client_sdr_id (int): The client SDR id.
        archetype_id (int): The archetype id.

    Returns:
        bool: True if the prospect is an ICP, False otherwise.
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

        # Create Prompt
        prompt += f"""\n\nHere is a potential prospect:
        Title: {prospect.title}
        LinkedIn Bio: {prospect.linkedin_bio}\n\n"""

        prompt += HARD_CODE_ICP_PROMPT

        # Generate Completion
        completion = wrapped_chat_gpt_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        fit = completion.split("Fit:")[1].split("Reason:")[0].strip()
        fit = int(fit)
        reason = completion.split("Reason:")[1].strip()

        # Update Prospect
        prospect.icp_fit_score = fit
        prospect.icp_fit_reason = reason

        # Charge the SDR credits
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client_sdr.icp_matching_credits -= 1

        db.session.add_all([client_sdr, prospect])
        db.session.commit()

        run_and_assign_intent_score(prospect_id)
        return True

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
        prospect.icp_fit_reason = f"Unknown Error: {e}"
        db.session.add(prospect)
        db.session.commit()

        raise self.retry(exc=Exception("Retrying task"))


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
