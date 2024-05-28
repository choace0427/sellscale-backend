from app import db, app
from model_import import AdversaryTrainingPoint, GeneratedMessage
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_generated_message,
)
from tests.test_utils.decorators import use_app_context
import json
import mock


fake_openai_response = {"choices": [{"text": "test completion    "}]}


def setup_generated_message():
    """Helper method to setup a generated message for testing. Removes redundant code.

    Returns:
        GeneratedMessage: A generated message object
    """
    c = basic_client()
    archetype = basic_archetype(client=c)
    prospect = basic_prospect(client=c, archetype=archetype)
    generated_message = basic_generated_message(prospect=prospect)
    return generated_message


@use_app_context
@mock.patch("openai.Completion.create", return_value=fake_openai_response)
def test_preview_fix_controller(openai_patch):
    response = app.test_client().post(
        "adversary/preview_fix",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "completion": "test completion",
                "fix": "test fix",
            }
        ),
    )
    assert openai_patch.called == 1
    assert response.status_code == 200
    assert response.json["preview"] == "test completion"


@use_app_context
def test_create_adversary():
    generated_message: GeneratedMessage = setup_generated_message()
    response = app.test_client().post(
        "adversary/create",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "generated_message_id": generated_message.id,
                "mistake_description": "test-mistake",
                "fix_instructions": "test-fix",
            }
        ),
    )
    assert response.status_code == 200

    training_point = AdversaryTrainingPoint.query.filter_by(
        generated_message_id=generated_message.id
    ).first()
    assert training_point is not None
    assert training_point.mistake_description == "test-mistake"
    assert training_point.fix_instuctions == "test-fix"


@use_app_context
def test_toggle_training_point():
    generated_message: GeneratedMessage = setup_generated_message()
    training_point = AdversaryTrainingPoint(
        generated_message_id=generated_message.id,
        prompt=generated_message.prompt,
        completion=generated_message.completion,
        mistake_description="test-mistake",
        fix_instuctions="test-fix",
        use_in_training=False,
        used_in_past_training=False,
    )
    db.session.add(training_point)
    db.session.commit()

    assert training_point.use_in_training == False
    response = app.test_client().post(
        "adversary/toggle_point",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "training_point_id": training_point.id,
                "toggle_on": True,
            }
        ),
    )
    assert response.status_code == 200
    training_point = AdversaryTrainingPoint.query.get(training_point.id)
    assert training_point.use_in_training == True

    response = app.test_client().post(
        "adversary/toggle_point",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "training_point_id": training_point.id,
                "toggle_on": False,
            }
        ),
    )
    assert response.status_code == 200
    training_point = AdversaryTrainingPoint.query.get(training_point.id)
    assert training_point.use_in_training == False


@use_app_context
def test_edit_training_point():
    generated_message: GeneratedMessage = setup_generated_message()
    training_point = AdversaryTrainingPoint(
        generated_message_id=generated_message.id,
        prompt=generated_message.prompt,
        completion=generated_message.completion,
        mistake_description="test-mistake",
        fix_instuctions="test-fix",
        use_in_training=False,
        used_in_past_training=False,
    )
    db.session.add(training_point)
    db.session.commit()

    response = app.test_client().post(
        "adversary/edit",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "training_point_id": training_point.id,
                "mistake_description": "test-mistake-edited",
                "fix_instructions": "test-fix-edited",
            }
        ),
    )
    assert response.status_code == 200
    training_point = AdversaryTrainingPoint.query.get(training_point.id)
    assert training_point.mistake_description == "test-mistake-edited"
    assert training_point.fix_instuctions == "test-fix-edited"
