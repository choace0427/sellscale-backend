from app import db

from model_import import AdversaryTrainingPoint, GeneratedMessage


def create_adversary_training_point(generated_message_id: int, mistake: str, fix: str):
    """ Creates a new training point for the adversary model.

    Args:
        generated_message_id (int): ID of the generated message to create a training point for.
        mistake (str): Mistake identified in the generated message
        fix (str): Proposed fix for the generated message

    Returns:
        status: 200 if successful, 404 if message not found, 400 if mistake or fix not provided.
    """
    message = GeneratedMessage.query.get(generated_message_id)
    if not message:
        return "Message not found", 404

    if mistake is None or fix is None:
        return "Mistake or fix not provided", 400

    if len(AdversaryTrainingPoint.query.filter_by(generated_message_id=generated_message_id).all()) == 1:
        return "Training point already exists", 400

    training_point = AdversaryTrainingPoint(
        generated_message_id=generated_message_id,
        prompt=message.prompt,
        completion=message.completion,
        mistake_description=mistake,
        fix_instuctions=fix,
        use_in_training=False,
        used_in_past_training=False
    )
    db.session.add(training_point)
    db.session.commit()

    return "Training point {} created".format(training_point.id), 200


def toggle_adversary_training_point(training_point_id: int, toggle_on: bool = False):
    """ Toggles the use_in_training flag for a training point.

    Args:
        training_point_id (int): ID of the training point to toggle.
        toggle_on (bool, optional): Value to set the training point. Defaults to False.

    Returns:
        status: 200 if successful, 404 if training point not found.
    """
    training_point: AdversaryTrainingPoint = AdversaryTrainingPoint.query.get(training_point_id)
    if not training_point:
        return "Training point not found", 404

    training_point.use_in_training = toggle_on
    db.session.commit()

    return "Point {} toggled to {}".format(training_point.id, training_point.use_in_training), 200
    

def edit_adversary_training_point(training_point_id: int, mistake: str, fix: str):
    """ Edits a training point for the adversary model.

    Args:
        training_point_id (int): ID of the training point to edit.
        mistake (str): Mistake identified in the generated message
        fix (str): Proposed fix for the generated message

    Returns:
        status: 200 if successful, 404 if training point not found, 400 if mistake or fix not provided.
    """
    training_point: AdversaryTrainingPoint = AdversaryTrainingPoint.query.get(training_point_id)
    if not training_point:
        return "Training point not found", 404

    if mistake is None or fix is None:
        return "Mistake or fix must be provided", 400

    training_point.mistake_description = mistake
    training_point.fix_instuctions = fix
    db.session.commit()

    return "Training point {} edited".format(training_point.id), 200
