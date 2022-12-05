from app import db, app
from test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_generated_message,
    basic_gnlp_model,
    basic_prospect,
)
from decorators import use_app_context
from src.message_generation.services import *
from src.ml.models import GNLPFinetuneJobStatuses
from app import db
import mock
import json
from src.ml.services import (
    create_upload_jsonl_file,
    initiate_fine_tune_job,
    check_statuses_of_fine_tune_jobs,
)
from model_import import GNLPModelFineTuneJobs


@use_app_context
@mock.patch("src.ml.services.openai.File.create")
def test_create_upload_jsonl_file(create_file_mock):
    prompt_completion_dict = {"key": "value"}
    create_upload_jsonl_file(prompt_completion_dict)

    assert create_file_mock.called


@use_app_context
@mock.patch("src.ml.services.openai.File.create", return_value={"id": "123"})
@mock.patch("src.ml.services.openai.FineTune.create", return_value={"id": "456"})
def test_initiate_fine_tune_job(file_create_mock, fine_tune_create_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)

    initiate_fine_tune_job(archetype.id, [generated_message.id], gnlp_model.model_type)

    assert GNLPModelFineTuneJobs.query.count() == 1
    assert file_create_mock.called
    assert fine_tune_create_mock.called


@use_app_context
@mock.patch("src.ml.services.openai.FineTune.retrieve", return_value={"id": "123"})
def test_get_fine_tune_statuses(fine_tune_retrieve_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)

    initiate_fine_tune_job(archetype.id, [generated_message.id], gnlp_model.model_type)

    fine_tune_jobs: list = GNLPModelFineTuneJobs.query.all()
    fine_tune_jobs[0].status = GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
    db.session.add(fine_tune_jobs[0])
    db.session.commit()

    fine_tune_jobs = GNLPModelFineTuneJobs.query.all()
    assert len(fine_tune_jobs) == 1
    assert fine_tune_jobs[0].status == GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB

    check_statuses_of_fine_tune_jobs()
    assert fine_tune_retrieve_mock.call_count == 1
