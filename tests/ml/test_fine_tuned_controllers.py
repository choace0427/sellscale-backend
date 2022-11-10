from test_utils import (
    basic_client,
    basic_archetype,
    basic_gnlp_model,
    basic_prospect,
    basic_generated_message,
)
from decorators import use_app_context
from test_utils import test_app
from model_import import GNLPModelFineTuneJobs
from src.ml.models import GNLPFinetuneJobStatuses, GNLPModelType
from app import app
import json
import mock


@use_app_context
@mock.patch("src.ml.services.openai.FineTune.create", return_value={"id": 123})
@mock.patch("src.ml.services.openai.File.create", return_value={"id": 123})
def test_post_fine_tune_openai_outreach_model(openai_file_mock, openai_fine_tune_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    message = basic_generated_message(prospect, gnlp_model)
    message_id = message.id

    response = app.test_client().post(
        "/ml/fine_tune_openai_outreach_model",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_ids": [message_id],
                "archetype_id": archetype_id,
                "model_type": "OUTREACH",
            }
        ),
    )
    assert response.status_code == 200
    assert openai_file_mock.call_count == 1
    assert openai_fine_tune_mock.call_count == 1

    all_fine_tune_jobs = GNLPModelFineTuneJobs.query.all()
    assert len(all_fine_tune_jobs) == 1
    for i in all_fine_tune_jobs:
        job: GNLPModelFineTuneJobs = i
        assert job.status == GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
        assert job.model_type == GNLPModelType.OUTREACH


@use_app_context
@mock.patch("src.ml.services.openai.FineTune.create", return_value={"id": 123})
@mock.patch("src.ml.services.openai.File.create", return_value={"id": 123})
def test_post_fine_tune_openai_outreach_model_first_line_only(
    openai_file_mock, openai_fine_tune_mock
):
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    message = basic_generated_message(prospect, gnlp_model)
    message_id = message.id

    response = app.test_client().post(
        "/ml/fine_tune_openai_outreach_model",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_ids": [message_id],
                "archetype_id": archetype_id,
                "model_type": "EMAIL_FIRST_LINE",
            }
        ),
    )
    assert response.status_code == 200
    assert openai_file_mock.call_count == 1
    assert openai_fine_tune_mock.call_count == 1

    all_fine_tune_jobs = GNLPModelFineTuneJobs.query.all()
    assert len(all_fine_tune_jobs) == 1
    for i in all_fine_tune_jobs:
        job: GNLPModelFineTuneJobs = i
        assert job.status == GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
        assert job.model_type == GNLPModelType.EMAIL_FIRST_LINE
