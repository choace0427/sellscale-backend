from datetime import datetime
from db import db
import os
from src.client.models import Client
from src.message_generation.models import GeneratedMessage
from src.ml.models import (
    GNLPFinetuneJobStatuses,
    GNLPModel,
    GNLPModelFineTuneJobs,
    GNLPModelType,
    ModelProvider,
)
import openai


def create_upload_jsonl_file(prompt_completion_dict: any):
    with open("training_set_temp.jsonl", "w") as f:
        for key in prompt_completion_dict:
            sanitized_key = key.replace('"', "")
            sanitized_value = prompt_completion_dict[key].replace('"', "")

            f.write(
                "{"
                + '"prompt":"{}","completion":"{} XXX"'.format(
                    sanitized_key, sanitized_value
                ).replace("\n", "\\n")
                + "}\n"
            )
        f.close()

    jsonl_file_upload = openai.File.create(
        file=open("training_set_temp.jsonl"), purpose="fine-tune"
    )
    return jsonl_file_upload


def initiate_fine_tune_job(
    client_id: int, message_ids: list, model_type: GNLPModelType
):
    # create new fine tune job in db
    job: GNLPModelFineTuneJobs = GNLPModelFineTuneJobs(
        client_id=client_id,
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
        job.client_id = client_id
        job.status = GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
        db.session.add(job)
        db.session.commit()

        return True, job, "OK"
    except Exception as e:
        # if failed update status
        job.status = GNLPFinetuneJobStatuses.FAILED
        job.error = str(e)
        db.session.add(job)
        db.session.commit()

        return False, job, str(e)


def check_statuses_of_fine_tune_jobs():
    jobs: list = (
        GNLPModelFineTuneJobs.query.filter(
            GNLPModelFineTuneJobs.status != GNLPFinetuneJobStatuses.COMPLETED
        )
        .filter(GNLPModelFineTuneJobs.status != GNLPFinetuneJobStatuses.FAILED)
        .all()
    )

    updated_job_ids = []
    for j in jobs:
        job: GNLPModelFineTuneJobs = j
        client: Client = Client.query.get(job.client_id)
        fine_tune_status = openai.FineTune.retrieve(id=job.finetune_job_id)
        model_uuid = fine_tune_status.get("fine_tuned_model")
        client_id = client.id

        if model_uuid:
            gnlp_model: GNLPModel = GNLPModel(
                model_provider=ModelProvider.OPENAI_GPT3,
                model_type=job.model_type,
                model_description="{client}-{date}".format(
                    client=client.company,
                    date=str(datetime.utcnow())[0:10],
                ),
                model_uuid=model_uuid,
                client_id=client_id,
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
