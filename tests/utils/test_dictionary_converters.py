from app import db
from src.utils.converters.dictionary_converters import dictionary_normalization
from tests.test_utils.decorators import use_app_context
import mock


@use_app_context
def test_dictionary_normalization():
    keys = set(["key1", "key2", "key3"])
    dictionaries = [
        {"key1": "value1", "key2": "value2"},
        {"key1": "value1", "key3": "value3"},
    ]
    assert dictionary_normalization(keys, dictionaries) is True
    assert dictionaries == [
        {"key1": "value1", "key2": "value2", "key3": None},
        {"key1": "value1", "key2": None, "key3": "value3"},
    ]
