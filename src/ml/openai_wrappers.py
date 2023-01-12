""" This file will hold wrappers for OpenAI APIs.

Eventual migration to these wrappers will aid in uniform testing and debugging.
"""

import openai
import os
from typing import Optional, Union

OPENAI_KEY = os.environ.get("OPENAI_KEY")
openai.api_key = OPENAI_KEY

CURRENT_OPENAI_DAVINCI_MODEL = "text-davinci-003"

def wrapped_create_completion(
        model: str,
        prompt: str,
        suffix: Optional[Union[str, list]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        stop: Optional[Union[str, list]] = None):
    """ Wrapper for OpenAI's Completion API.

    Only model and prompt are required
    """
    
    response = openai.Completion.create(
        model=model,
        prompt=prompt,
        suffix=suffix,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        n=n,
        frequency_penalty=frequency_penalty,
        stop=stop,
    )
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return ""

    choices = response['choices']
    top_choice = choices[0]
    preview = top_choice['text'].strip()
    return preview
