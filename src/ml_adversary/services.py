import openai
import os

from app import db
from model_import import (
    AdversaryTrainingPoint,
    GeneratedMessage,
    AdversaryFineTuneHistory,
)

openai.api_key = os.getenv("OPENAI_KEY")


def run_adversary(prompt: str, completion: str):
    """Runs the adversary model on a given prompt and completion.

    Args:
        prompt (str): Prompt to run the adversary model on.
        completion (str): Completion to run the adversary model on.

    Returns:
        str: Adversary model's output.
    """
    if prompt == "" or completion == "":
        raise ValueError("Prompt or completion not provided")

    max_tokens_length = 200
    prompt = prompt.strip()
    completion = completion.strip()

    tune_history: AdversaryFineTuneHistory = AdversaryFineTuneHistory.query.filter_by(
        active=True
    ).first()
    current_model = tune_history.model_name

    processed_prompt = (
        "instruction: Given the prompt and the completion, find the mistake in the completion, if any. If mistake found, propose a fix."
        + "\n---\n"
        + 'prompt: """'
        + prompt
        + '"""'
        + "\n---\n"
        + 'completion: """'
        + completion
        + '"""'
        + "\n---\n"
        + "mistake:"
    )

    response = openai.Completion.create(
        model=current_model,
        prompt=processed_prompt,
        max_tokens=max_tokens_length,
        temperature=0.1,
        stop=["XXX_END_GEN_XXX"],
    )
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return "Error generating adversary output", 400

    choices = response["choices"]
    top_choice = choices[0]
    adversary_output = top_choice["text"].strip()

    mistake, fix = get_mistake_fix_from_adversary_output(adversary_output)

    return mistake, fix, 200


def get_mistake_fix_from_adversary_output(adversary_output: str):
    """Gets the mistake and fix from the adversary output.

    Args:
        adversary_output (str): Adversary output to parse.

    Returns:
        str: Mistake identified by the adversary model.
        str: Fix proposed by the adversary model.
    """
    if adversary_output == "":
        raise ValueError("Adversary output not provided")

    splitted = adversary_output.split("\n---\n")
    full_mistake, full_fix = splitted[0].strip(), splitted[1].strip()
    stripped_mistake = full_mistake.replace('"""', "").strip()
    stripped_fix = full_fix.replace('"""', "").replace("fix: ", "").strip()

    return stripped_mistake, stripped_fix


def preview_fix(completion: str, fix: str):
    """Previews the fix for a given completion.

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
        model="gpt-3.5-turbo",
        prompt="completion: {}\nfix: {}\ncompletion:".format(completion, fix),
        max_tokens=max_tokens_length,
        temperature=0,
    )
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return "Error generating preview", 400

    choices = response["choices"]
    top_choice = choices[0]
    preview = top_choice["text"].strip()

    return preview, 200


def create_adversary_training_point(generated_message_id: int, mistake: str, fix: str):
    """Creates a new training point for the adversary model.

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

    if (
        len(
            AdversaryTrainingPoint.query.filter_by(
                generated_message_id=generated_message_id
            ).all()
        )
        == 1
    ):
        return "Training point already exists", 400

    training_point = AdversaryTrainingPoint(
        generated_message_id=generated_message_id,
        prompt=message.prompt,
        completion=message.completion,
        mistake_description=mistake,
        fix_instuctions=fix,
        use_in_training=False,
        used_in_past_training=False,
    )
    db.session.add(training_point)
    db.session.commit()

    return "Training point {} created".format(training_point.id), 200


def toggle_adversary_training_point(training_point_id: int, toggle_on: bool = False):
    """Toggles the use_in_training flag for a training point.

    Args:
        training_point_id (int): ID of the training point to toggle.
        toggle_on (bool, optional): Value to set the training point. Defaults to False.

    Returns:
        status: 200 if successful, 404 if training point not found.
    """
    training_point: AdversaryTrainingPoint = AdversaryTrainingPoint.query.get(
        training_point_id
    )
    if not training_point:
        return "Training point not found", 404

    training_point.use_in_training = toggle_on
    db.session.commit()

    return (
        "Point {} toggled to {}".format(
            training_point.id, training_point.use_in_training
        ),
        200,
    )


def edit_adversary_training_point(training_point_id: int, mistake: str, fix: str):
    """Edits a training point for the adversary model.

    Args:
        training_point_id (int): ID of the training point to edit.
        mistake (str): Mistake identified in the generated message
        fix (str): Proposed fix for the generated message

    Returns:
        status: 200 if successful, 404 if training point not found, 400 if mistake or fix not provided.
    """
    training_point: AdversaryTrainingPoint = AdversaryTrainingPoint.query.get(
        training_point_id
    )
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
