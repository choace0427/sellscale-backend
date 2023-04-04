from datetime import datetime
from typing import List
from app import db, celery
import os
from src.client.models import Client, ClientArchetype, ClientSDR
from src.message_generation.models import GeneratedMessage
from src.ml.models import (
    GNLPFinetuneJobStatuses,
    GNLPModel,
    GNLPModelFineTuneJobs,
    GNLPModelType,
    ModelProvider,
)
from src.ml.openai_wrappers import wrapped_create_completion, CURRENT_OPENAI_DAVINCI_MODEL, CURRENT_OPENAI_CHAT_GPT_MODEL
import regex as rx
import re

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
        max_tokens=len(completion)+10,
    )

    return fixed_completion


def get_sequence_value_props(company: str, selling_to: str, selling_what: str, num: int):

    prompt = f"You are a writing assistant that helps write email sequences. Here is the information:\n"
    prompt += f"- Company: {company}\n"
    prompt += f"- Who are you selling to?: {selling_to}\n"
    prompt += f"- What are you selling?: {selling_what}\n"
    prompt += f"- Number of emails in the sequence: {num}\n"
    prompt += "\n\nBased on this information, generate {num} value props we can use to target. Each value prop should be a 5-10 word phrase with a hyphen and one sentance describing it in detail.".format(num=num)

    fixed_completion = wrapped_create_completion(
        model=CURRENT_OPENAI_DAVINCI_MODEL,
        prompt=prompt,
        temperature=1,
        max_tokens=20+30*num,
    )

    props = re.sub(r'\d+\. ', '', fixed_completion).split('\n')
    return props


def get_sequence_draft(value_props: list[str], client_sdr_id: int, archetype_id: int) -> list[dict]:
    """ Generates a sequence draft for a client.

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
    prompt += f"- Write a sequence of emails that targets the value props and persona.\n"
    prompt += f"- The emails need to address the recipient using {{{{first_name}}}} as a placeholder for the first name.\n"
    prompt += f"- The emails need to build off of each other.\n"
    prompt += f"- The second email should open with a question.\n"
    prompt += f"- The third email should reference results or a case study.\n"
    prompt += f"- Limit the sequence to 3 emails.\n"
    prompt += f"- In only the first email, you must include {{{{{personalization_field_name}}}}} after the salutation but before the introduction and body.\n"
    prompt += f"- Do not include other custom fields in the completion.\n"
    prompt += f"- Sign the email using 'Best' and the Sales Person's name.\n"
    prompt += f"- Output in the form of a JSON array with a dictionary representation of 'subject_line' and 'email'.\n"

    # Prompt Engineering - Finish
    prompt += f"\nSequence:"

    # Generate Completion
    emails = wrapped_create_completion(
        # TODO: Use CURRENT_OPENAI_LATEST_GPT_MODEL when we gain access.
        model=CURRENT_OPENAI_DAVINCI_MODEL,
        prompt=prompt,
        temperature=0.7,
        frequency_penalty=1.15,
        max_tokens=600,
    )

    # Parse Completion
    parsed_emails = []
    json_emails: list[dict] = json.loads(emails)
    for email in json_emails:
        parsed_emails.append({
            'subject_line': email.get('subject_line'),
            'email': email.get('email'),
        })

    return parsed_emails
