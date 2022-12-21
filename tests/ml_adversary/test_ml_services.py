from app import db, app
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_gnlp_model,
    basic_generated_message,
)
from src.ml_adversary.services import (
    create_adversary_training_point,
    toggle_adversary_training_point,
    edit_adversary_training_point,
)
from model_import import (AdversaryTrainingPoint, GeneratedMessage)
from decorators import use_app_context


def setup_generated_message():
    """ Helper method to setup a generated message for testing. Removes redundant code.

    Returns:
        GeneratedMessage: A generated message object
    """
    c = basic_client()
    archetype = basic_archetype(client=c)
    prospect = basic_prospect(client=c, archetype=archetype)
    gnlp_model = basic_gnlp_model(archetype=archetype)
    generated_message = basic_generated_message(prospect=prospect, gnlp_model=gnlp_model)
    return generated_message


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
    atp = AdversaryTrainingPoint.query.filter_by(generated_message_id=generated_message.id).first()
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
    atp = AdversaryTrainingPoint.query.filter_by(generated_message_id=generated_message.id).all()
    assert len(atp) == 1

    # Test that we can't create a adversary training point without a mistake
    response = create_adversary_training_point(
        generated_message_id=generated_message2.id,
        mistake=None,
        fix="test fix"
    )
    _, status_code = response[0], response[1]
    assert status_code == 400
    atp = AdversaryTrainingPoint.query.filter_by(generated_message_id=generated_message2.id).all()
    assert len(atp) == 0

    # Test that we can't create a adversary training point without a fix
    response = create_adversary_training_point(
        generated_message_id=generated_message2.id,
        mistake="test mistake",
        fix=None
    )
    _, status_code = response[0], response[1]
    assert status_code == 400
    atp = AdversaryTrainingPoint.query.filter_by(generated_message_id=generated_message2.id).all()


@use_app_context
def test_toggle_adversary_training_point():
    # Test that we can't toggle a non-existent training point
    response = toggle_adversary_training_point(training_point_id=1, toggle_on=False)
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
    atp = AdversaryTrainingPoint.query.filter_by(generated_message_id=generated_message.id).first()
    assert atp.use_in_training == False

    # Test that we can toggle a training point
    response = toggle_adversary_training_point(training_point_id=atp.id, toggle_on=True)
    _, status_code = response[0], response[1]
    assert status_code == 200
    assert atp.use_in_training == True

    # Test that we can toggle a training point
    response = toggle_adversary_training_point(training_point_id=atp.id, toggle_on=False)
    _, status_code = response[0], response[1]
    assert status_code == 200
    assert atp.use_in_training == False


@use_app_context
def test_edit_adversary_training_point():
    # Test that we can't edit a non-existent training point
    response = edit_adversary_training_point(training_point_id=1, mistake="test mistake", fix="test fix")
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
    atp = AdversaryTrainingPoint.query.filter_by(generated_message_id=generated_message.id).first()

    # Test that we can edit a training point
    response = edit_adversary_training_point(training_point_id=atp.id, mistake="test mistake 2", fix="test fix 2")
    _, status_code = response[0], response[1]
    assert status_code == 200
    assert atp.mistake_description == "test mistake 2"
    assert atp.fix_instuctions == "test fix 2"

    # Test that we can't edit a training point without a mistake
    response = edit_adversary_training_point(training_point_id=atp.id, mistake=None, fix="test fix 3")
    _, status_code = response[0], response[1]
    assert status_code == 400
    assert atp.mistake_description == "test mistake 2"
    assert atp.fix_instuctions == "test fix 2"

    # Test that we can't edit a training point without a fix
    response = edit_adversary_training_point(training_point_id=atp.id, mistake="test mistake 3", fix=None)
    _, status_code = response[0], response[1]
    assert status_code == 400
    assert atp.mistake_description == "test mistake 2"
    assert atp.fix_instuctions == "test fix 2"
