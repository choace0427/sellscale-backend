import openai
import os

from app import db
from model_import import AdversaryTrainingPoint, GeneratedMessage

openai.api_key = os.getenv("OPENAI_KEY")

def preview_fix(completion: str, fix: str):
    """ Previews the fix for a given completion.

    Args:
        completion (str): Completion to preview the fix for.
        fix (str): Fix to preview.

    Returns:
        str: Preview of the fix.
    """
    if completion == "" or fix == "":
        return "Completion or fix not provided", 400

    # Define the maximum number of generated tokens to be equal to 1.25 the original message.
    max_tokens_length = int(len(completion) * 1.25)
    completion = completion.strip()
    fix = fix.strip()

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="completion: {}\nfix: {}\ncompletion:".format(completion, fix),
        max_tokens=max_tokens_length,
        temperature=0,
    )
    if response is None or response['choices'] is None or len(response['choices']) == 0:
        return "Error generating preview", 400

    choices = response['choices']
    top_choice = choices[0]
    preview = top_choice['text'].strip()     

    return preview, 200


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
    training_point.use_in_training = False
    training_point.used_in_past_training = False
    db.session.commit()

    return "Training point {} edited".format(training_point.id), 200
