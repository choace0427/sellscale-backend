""" This file will hold wrappers for OpenAI APIs.

Eventual migration to these wrappers will aid in uniform testing and debugging.
"""

import random
import time
import openai
import os
from typing import Optional, Union

OPENAI_KEY = os.environ.get("OPENAI_KEY")
openai.api_key = OPENAI_KEY


OPENAI_COMPLETION_DAVINCI_3_MODEL = "text-davinci-003"
NEWEST_COMPLETION_MODEL = OPENAI_COMPLETION_DAVINCI_3_MODEL
COMPLETION_MODELS = [OPENAI_COMPLETION_DAVINCI_3_MODEL]

OPENAI_CHAT_GPT_4_MODEL = "gpt-4"
OPENAI_CHAT_GPT_3_5_TURBO_MODEL = "gpt-3.5-turbo"
NEWEST_CHAT_GP_MODEL = OPENAI_CHAT_GPT_4_MODEL
CHAT_GPT_MODELS = [OPENAI_CHAT_GPT_4_MODEL, OPENAI_CHAT_GPT_3_5_TURBO_MODEL]

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
    stop: Optional[Union[str, list]] = DEFAULT_STOP,
) -> Union[str, bool]:
    """Wrapper for OpenAI's Completion.create() function.

    Args:
        model (str): The model to use for completion.
        prompt (str): The prompt to use for completion.
        suffix (Optional[Union[str, list]], optional): The suffix that comes after a completion of inserted text. Defaults to DEFAULT_SUFFIX.
        max_tokens (Optional[int], optional): The maximum number of tokens to generate in the completion. Defaults to DEFAULT_MAX_TOKENS.
        temperature (Optional[float], optional): What sampling temperature to use. Higher values means the model will take more risks. Try 0.9 for more creative applications, and 0 (argmax sampling) for ones with a well-defined answer. Defaults to DEFAULT_TEMPERATURE.
        top_p (Optional[float], optional): An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability mass are considered.. Defaults to DEFAULT_TOP_P.
        n (Optional[int], optional): How many completions to generate for each prompt. Defaults to DEFAULT_N.
        frequency_penalty (Optional[float], optional): Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim. Defaults to DEFAULT_FREQUENCY_PENALTY.
        stop (Optional[Union[str, list]], optional): Up to 4 sequences where the API will stop generating further tokens. The returned text will not contain the stop sequence. Defaults to DEFAULT_STOP.

    Returns:
        str: The top completion generated by the model.

    DEFAULT_SUFFIX: None
    DEFAULT_MAX_TOKENS: 16
    DEFAULT_TEMPERATURE: 1
    DEFAULT_TOP_P: 1
    DEFAULT_N: 1
    DEFAULT_FREQUENCY_PENALTY: 0
    DEFAULT_STOP: None
    """
    try:
        if model in CHAT_GPT_MODELS:
            return wrapped_chat_gpt_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                n=n,
                frequency_penalty=frequency_penalty,
                stop=stop,
            )
        else:
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
            if (
                response is None
                or response["choices"] is None
                or len(response["choices"]) == 0
            ):
                return ""

            choices = response["choices"]
            top_choice = choices[0]
            preview = top_choice["text"].strip()
            return preview
    except Exception as e:
        print(e)
        return False


def wrapped_chat_gpt_completion(
    messages: list,
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS,
    temperature: Optional[float] = DEFAULT_TEMPERATURE,
    top_p: Optional[float] = DEFAULT_TOP_P,
    n: Optional[int] = DEFAULT_N,
    frequency_penalty: Optional[float] = DEFAULT_FREQUENCY_PENALTY,
    stop: Optional[Union[str, list]] = DEFAULT_STOP,
    model: str = OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
    max_attempts: int = 3,
) -> str:
    """
    Generates a completion using the GPT-3.5-turbo model.

    messages needs to be in the format:
    [
        {
            "role": "user",
            "content": "Hello, how are you?"
        },
        {
            "role": "bot",
            "content": "I am doing well, how about you?"
        }
        ...
    ]
    """
    response = attempt_chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        n=n,
        frequency_penalty=frequency_penalty,
        stop=stop,
        model=model,
        max_attempts=max_attempts,
    )
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return ""

    choices = response["choices"]
    top_choice = choices[0]
    preview = top_choice["message"]["content"].strip()
    return preview


def wrapped_chat_gpt_completion_with_history(
    messages: list,
    history: Optional[list] = [],
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS,
    temperature: Optional[float] = DEFAULT_TEMPERATURE,
    top_p: Optional[float] = DEFAULT_TOP_P,
    n: Optional[int] = DEFAULT_N,
    frequency_penalty: Optional[float] = DEFAULT_FREQUENCY_PENALTY,
    stop: Optional[Union[str, list]] = DEFAULT_STOP,
    model: str = OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
    max_attempts: int = 3,
) -> tuple[list, str]:
    """
    Generates a completion using the GPT-3.5-turbo model.

    messages needs to be in the format:
    [
        {
            "role": "user",
            "content": "Hello, how are you?"
        },
        {
            "role": "assistant",
            "content": "I am doing well, how about you?"
        }
        ...
    ]
    """
    if history:
        messages = history + messages

    response = attempt_chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        n=n,
        frequency_penalty=frequency_penalty,
        stop=stop,
        model=model,
        max_attempts=max_attempts,
    )
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return ""

    choices = response["choices"]
    top_choice = choices[0]
    preview = top_choice["message"]["content"].strip()

    messages = messages + [{"role": "assistant", "content": preview}]
    return messages, preview


def attempt_chat_completion(
    messages: list,
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS,
    temperature: Optional[float] = DEFAULT_TEMPERATURE,
    top_p: Optional[float] = DEFAULT_TOP_P,
    n: Optional[int] = DEFAULT_N,
    frequency_penalty: Optional[float] = DEFAULT_FREQUENCY_PENALTY,
    stop: Optional[Union[str, list]] = DEFAULT_STOP,
    model: str = OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
    max_attempts: int = 3,
):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                n=n,
                frequency_penalty=frequency_penalty,
                stop=stop,
            )
            return response
        except Exception as e:
            attempts += 1
            # Add a random delay before the next attempt
            time.sleep(random.uniform(0.5, 1.5))
    print(f"OpenAI chat completion exceeded maximum attempts ({max_attempts})!")
    raise Exception("OpenAI chat completion exceeded maximum attempts!")
