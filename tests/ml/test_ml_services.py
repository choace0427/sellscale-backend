from app import db, app
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_generated_message,
    basic_gnlp_model,
    basic_prospect,
)
from tests.test_utils.decorators import use_app_context
from src.message_generation.services import *
from src.ml.models import GNLPFinetuneJobStatuses
from app import db
import mock
import json
from src.ml.services import (
    chat_ai_classify_active_convo,
    create_upload_jsonl_file,
    initiate_fine_tune_job,
    check_statuses_of_fine_tune_jobs,
    get_aree_fix_basic,
    get_sequence_value_props,
    get_icp_classification_prompt_by_archetype_id,
    patch_icp_classification_prompt,
    icp_classify,
)
from model_import import GNLPModelFineTuneJobs, ClientSDR


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

    initiate_fine_tune_job(
        archetype.id, [generated_message.id], gnlp_model.model_type)

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

    initiate_fine_tune_job(
        archetype.id, [generated_message.id], gnlp_model.model_type)

    fine_tune_jobs: list = GNLPModelFineTuneJobs.query.all()
    fine_tune_jobs[0].status = GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB
    db.session.add(fine_tune_jobs[0])
    db.session.commit()

    fine_tune_jobs = GNLPModelFineTuneJobs.query.all()
    assert len(fine_tune_jobs) == 1
    assert fine_tune_jobs[0].status == GNLPFinetuneJobStatuses.STARTED_FINE_TUNE_JOB

    check_statuses_of_fine_tune_jobs()
    assert fine_tune_retrieve_mock.call_count == 1


@use_app_context
@mock.patch("src.ml.services.wrapped_create_completion", return_value="test")
def test_get_aree_fix_basic(create_completion_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id

    # No problems
    response = get_aree_fix_basic(generated_message.id)
    assert create_completion_mock.call_count == 0
    assert response == generated_message.completion

    # Has problems
    generated_message.problems = ["problem1", "problem2"]
    db.session.add(generated_message)
    db.session.commit()
    response = get_aree_fix_basic(generated_message_id)
    assert create_completion_mock.call_count == 1
    assert response == "test"


@use_app_context
@mock.patch("src.ml.services.wrapped_create_completion", return_value="test")
def test_get_sequence_value_props(create_completion_mock):

    # No problems
    response = get_sequence_value_props("Test", "Test", "Test", 1)
    assert create_completion_mock.call_count == 1
    assert response == ["test"]


@use_app_context
def test_get_icp_classification_prompt_by_archetype_id():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype.icp_matching_prompt = "test"

    prompt, filters = get_icp_classification_prompt_by_archetype_id(archetype.id)
    assert prompt == archetype.icp_matching_prompt
    assert filters == archetype.icp_matching_option_filters


@use_app_context
def test_patch_icp_classification_prompt():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype.icp_matching_prompt = "test"

    assert archetype.icp_matching_prompt == "test"
    patch_icp_classification_prompt(archetype.id, "test2")
    assert archetype.icp_matching_prompt == "test2"


@use_app_context
@mock.patch(
    "src.ml.services.wrapped_chat_gpt_completion",
    return_value="Fit: 6\nReason: Some reason",
)
def test_icp_classify(wrapped_chat_gpt_completion_mock):
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    sdr.ml_credits = 1
    archetype = basic_archetype(client, sdr)
    archetype.icp_matching_prompt = "test"
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id

    assert prospect.icp_fit_score is None
    assert prospect.icp_fit_reason is None
    result = icp_classify(prospect.id, sdr.id, archetype.id)
    assert wrapped_chat_gpt_completion_mock.call_count == 1
    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.icp_fit_score == 6
    assert prospect.icp_fit_reason == "Some reason"
    sdr: ClientSDR = ClientSDR.query.get(sdr_id)
    assert sdr.ml_credits == 0


@use_app_context
@mock.patch(
    "src.ml.services.wrapped_chat_gpt_completion",
    return_value="4",
)
def test_chat_ai_classify_active_convo(mock_chat_gpt_completion):
    messages = ["David: Hey Aakash, would you like to buy an AI solution from me",
                "Aakash: Not at the moment, I am a bit busy"]
    result = chat_ai_classify_active_convo(messages, "David")
    assert result == ProspectStatus.ACTIVE_CONVO_CIRCLE_BACK
    assert mock_chat_gpt_completion.call_count == 1

    with mock.patch("src.ml.services.wrapped_chat_gpt_completion",
                    return_value="error") as mock_chat_gpt_completion:
        result = chat_ai_classify_active_convo(messages, "David")
        assert result == ProspectStatus.ACTIVE_CONVO_NEXT_STEPS
        assert mock_chat_gpt_completion.call_count == 1
