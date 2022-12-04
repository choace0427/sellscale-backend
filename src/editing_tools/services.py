import openai


def magic_edit(message_copy: str):
    """
    Makes edits to message copy to make it more natural and fix spelling and returns 4 choices.
    """
    instruction = "Make adjustments to this paragraph to make it sound more natural and fix any spelling errors."

    return get_edited_options(instruction=instruction, message_copy=message_copy)


def shorten(message_copy: str):
    """
    Shortens message copy using GPT-3.
    """
    instruction = "Make this 10% shorter."

    return get_edited_options(instruction=instruction, message_copy=message_copy)


def get_edited_options(instruction: str, message_copy: str):
    """
    Makes edits prescribed in instruction to message copy and returns 4 choices.
    """
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="instruction:\n{instruction}\n\ninput:\n{message_copy}\n\noutput:".format(
            instruction=instruction, message_copy=message_copy
        ),
        temperature=0.7,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        n=4,
    )
    return [choice["text"] for choice in response["choices"]]
