""" This file will hold wrappers for OpenAI APIs.

Eventual migration to these wrappers will aid in uniform testing and debugging.
"""

import openai
import os
from typing import Optional, Union

OPENAI_KEY = os.environ.get("OPENAI_KEY")
openai.api_key = OPENAI_KEY

CURRENT_OPENAI_DAVINCI_MODEL = "text-davinci-003"
DEFAULT_SUFFIX = None
DEFAULT_MAX_TOKENS = 16
DEFAULT_TEMPERATURE = 1
DEFAULT_TOP_P = 1
DEFAULT_N = 1
DEFAULT_FREQUENCY_PENALTY = 0
DEFAULT_STOP = None

def wrapped_create_completion(
        model: str,
        prompt: str,
        suffix: Optional[Union[str, list]] = DEFAULT_SUFFIX,
        max_tokens: Optional[int] = DEFAULT_MAX_TOKENS,
        temperature: Optional[float] = DEFAULT_TEMPERATURE,
        top_p: Optional[float] = DEFAULT_TOP_P,
        n: Optional[int] = DEFAULT_N,
        frequency_penalty: Optional[float] = DEFAULT_FREQUENCY_PENALTY,
        stop: Optional[Union[str, list]] = DEFAULT_STOP):
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
