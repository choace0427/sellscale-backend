from app import db, app
from tests.test_utils.test_utils import test_app
from src.ml_adversary.services import (
    run_adversary,
    get_mistake_fix_from_adversary_output,
    preview_fix,
    create_adversary_training_point,
    toggle_adversary_training_point,
    edit_adversary_training_point,
)
from model_import import (AdversaryTrainingPoint, GeneratedMessage, AdversaryFineTuneHistory)
from tests.test_utils.decorators import use_app_context
import mock
import pytest

from helpers import (
    fake_openai_response,
    fake_openai_response_fail,
    fake_adversary_response,
    setup_generated_message
)


@use_app_context
@mock.patch("openai.Completion.create", return_value=fake_adversary_response)
def test_run_adversary(openai_patch):
    # Test that we can't run the adversary if the prompt OR completion is empty
    with pytest.raises(ValueError):
        run_adversary(prompt="", completion="test completion")
        run_adversary(prompt="test prompt", completion="")

    tune_history: AdversaryFineTuneHistory = AdversaryFineTuneHistory.query.filter_by(active=True).first()
    current_model = tune_history.model_name
    openai_prompt = "instruction: Given the prompt and the completion, find the mistake in the completion, if any. If mistake found, propose a fix.\n---\nprompt: \"\"\"test prompt\"\"\"\n---\ncompletion: \"\"\"test completion\"\"\"\n---\nmistake:"

    # Test that we can run the adversary
    response = run_adversary(prompt="test prompt", completion="test completion")
    mistake, fix, status_code = response[0], response[1], response[2]
    assert status_code == 200
    assert openai_patch.called == 1
    assert openai_patch.called_with(
        model=current_model,
        prompt=openai_prompt,
        max_tokens=200,
        temperature=0.1,
        stop=["XXX_END_GEN_XXX"],
    )
    assert mistake == "test mistake."
    assert fix == "test fix."


@use_app_context
def test_get_mistake_fix_from_adversary_output():
    with pytest.raises(ValueError):
        get_mistake_fix_from_adversary_output(adversary_output="")

    test_output =  "\"\"\"test mistake.\"\"\"\n---\nfix: \"\"\"test fix.\"\"\"\n---\n."

    mistake, fix = get_mistake_fix_from_adversary_output(adversary_output=test_output)
    assert mistake == "test mistake."
    assert fix == "test fix."


@use_app_context
@mock.patch("openai.Completion.create", return_value=fake_openai_response)
def test_preview_fix_success(openai_patch):
    # Test that we can't preview a fix if the completion is empty
    response = preview_fix(completion="", fix="test fix")
    _, status_code = response[0], response[1]
    assert status_code == 400
    assert openai_patch.called == 0

    # Test that we can't preview a fix if the fix is empty
    response = preview_fix(completion="test completion", fix="")
    _, status_code = response[0], response[1]
    assert status_code == 400
    assert openai_patch.called == 0

    # Test that we can preview a fix
    response = preview_fix(completion="test completion", fix="test fix")
    preview, status_code = response[0], response[1]
    assert openai_patch.called == 1
    assert preview == "test completion"
    assert status_code == 200


@use_app_context
@mock.patch("openai.Completion.create", return_value=fake_openai_response_fail)
def test_preview_fix_fail(openai_patch):
    # Test that we can't preview a fix if the response is bad
    response = preview_fix(completion="test completion", fix="test fix")
    _, status_code = response[0], response[1]
    assert status_code == 400
    assert openai_patch.called == 1


@use_app_context
def test_create_adversary_training_point():
    # Test that we can't create a adversary training point on a non-existent generated_message
    response = create_adversary_training_point(
        generated_message_id=1,
        mistake="test mistake",
        fix="test fix"
    )
    _, status_code = response[0], response[1]
    assert status_code == 404

    generated_message: GeneratedMessage = setup_generated_message()
    generated_message2: GeneratedMessage = setup_generated_message()

    # Test that we can create a new adversary training point
    response = create_adversary_training_point(
        generated_message_id=generated_message.id,
        mistake="test mistake",
        fix="test fix"
    )
    _, status_code = response[0], response[1]
    assert status_code == 200
    atp = AdversaryTrainingPoint.query.filter_by(
        generated_message_id=generated_message.id).first()
    assert atp.generated_message_id == generated_message.id
    assert atp.prompt == generated_message.prompt
    assert atp.completion == generated_message.completion
    assert atp.mistake_description == "test mistake"
    assert atp.fix_instuctions == "test fix"
    assert atp.use_in_training == False

    # Test that we can't create a adversary training point on the same generated_message
    response = create_adversary_training_point(
        generated_message_id=generated_message.id,
        mistake="test mistake",
        fix="test fix"
    )
    _, status_code = response[0], response[1]
    assert status_code == 400
    atp = AdversaryTrainingPoint.query.filter_by(
        generated_message_id=generated_message.id).all()
    assert len(atp) == 1

    # Test that we can't create a adversary training point without a mistake
    response = create_adversary_training_point(
        generated_message_id=generated_message2.id,
        mistake=None,
        fix="test fix"
    )
    _, status_code = response[0], response[1]
    assert status_code == 400
    atp = AdversaryTrainingPoint.query.filter_by(
        generated_message_id=generated_message2.id).all()
    assert len(atp) == 0

    # Test that we can't create a adversary training point without a fix
    response = create_adversary_training_point(
        generated_message_id=generated_message2.id,
        mistake="test mistake",
        fix=None
    )
    _, status_code = response[0], response[1]
    assert status_code == 400
    atp = AdversaryTrainingPoint.query.filter_by(
        generated_message_id=generated_message2.id).all()


@use_app_context
def test_toggle_adversary_training_point():
    # Test that we can't toggle a non-existent training point
    response = toggle_adversary_training_point(
        training_point_id=1, toggle_on=False)
    _, status_code = response[0], response[1]
    assert status_code == 404

    generated_message: GeneratedMessage = setup_generated_message()
    response = create_adversary_training_point(
        generated_message_id=generated_message.id,
        mistake="test mistake",
        fix="test fix"
    )
    _, status_code = response[0], response[1]
    assert status_code == 200
    atp = AdversaryTrainingPoint.query.filter_by(
        generated_message_id=generated_message.id).first()
    assert atp.use_in_training == False

    # Test that we can toggle a training point
    response = toggle_adversary_training_point(
        training_point_id=atp.id, toggle_on=True)
    _, status_code = response[0], response[1]
    assert status_code == 200
    assert atp.use_in_training == True

    # Test that we can toggle a training point
    response = toggle_adversary_training_point(
        training_point_id=atp.id, toggle_on=False)
    _, status_code = response[0], response[1]
    assert status_code == 200
    assert atp.use_in_training == False


@use_app_context
def test_edit_adversary_training_point():
    # Test that we can't edit a non-existent training point
    response = edit_adversary_training_point(
        training_point_id=1, mistake="test mistake", fix="test fix")
    _, status_code = response[0], response[1]
    assert status_code == 404

    generated_message: GeneratedMessage = setup_generated_message()
    response = create_adversary_training_point(
        generated_message_id=generated_message.id,
        mistake="test mistake",
        fix="test fix"
    )
    _, status_code = response[0], response[1]
    assert status_code == 200
    atp = AdversaryTrainingPoint.query.filter_by(
        generated_message_id=generated_message.id).first()

    # Test that we can edit a training point
    response = edit_adversary_training_point(
        training_point_id=atp.id, mistake="test mistake 2", fix="test fix 2")
    _, status_code = response[0], response[1]
    assert status_code == 200
    assert atp.mistake_description == "test mistake 2"
    assert atp.fix_instuctions == "test fix 2"

    # Test that we can't edit a training point without a mistake
    response = edit_adversary_training_point(
        training_point_id=atp.id, mistake=None, fix="test fix 3")
    _, status_code = response[0], response[1]
    assert status_code == 400
    assert atp.mistake_description == "test mistake 2"
    assert atp.fix_instuctions == "test fix 2"

    # Test that we can't edit a training point without a fix
    response = edit_adversary_training_point(
        training_point_id=atp.id, mistake="test mistake 3", fix=None)
    _, status_code = response[0], response[1]
    assert status_code == 400
    assert atp.mistake_description == "test mistake 2"
    assert atp.fix_instuctions == "test fix 2"

    atp.use_in_training = True
    atp.used_in_past_training = True

    # Test that we set the use_in_training to false when we edit a training point
    response = edit_adversary_training_point(
        training_point_id=atp.id, mistake="test mistake 4", fix="test fix 4")
    _, status_code = response[0], response[1]
    assert status_code == 200
    assert atp.mistake_description == "test mistake 4"
    assert atp.fix_instuctions == "test fix 4"
    assert atp.use_in_training == False
    assert atp.used_in_past_training == False
