from decorators import use_app_context
from test_utils import test_app
from app import app
import mock

from src.ml.openai_wrappers import *


@use_app_context
@mock.patch("openai.Completion.create", return_value={"choices": [{"text": "test"}]})
def test_wrapped_create_completion(openai_mock):
    response = wrapped_create_completion(
        model="test",
        prompt="test",
        suffix="test",
        max_tokens=1,
        temperature=1,
        top_p=1,
        n=1,
        frequency_penalty=1,
        stop="test-stop",
    )
    assert response == "test"
    assert openai_mock.call_count == 1
    assert openai_mock.call_args[1] == {
        "model": "test",
        "prompt": "test",
        "suffix": "test",
        "max_tokens": 1,
        "temperature": 1,
        "top_p": 1,
        "n": 1,
        "frequency_penalty": 1,
        "stop": "test-stop"
    }

    response = wrapped_create_completion(
        model="test",
        prompt="test"
    )
    assert response == "test"
    assert openai_mock.call_count == 2
    assert openai_mock.call_args[1] == {
        'model': 'test',
        'prompt': 'test',
        'suffix': None,
        'max_tokens': None,
        'temperature': None,
        'top_p': None,
        'n': None,
        'frequency_penalty': None,
        'stop': None
    }
