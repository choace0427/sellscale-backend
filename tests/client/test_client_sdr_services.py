from app import app, db
from decorators import use_app_context
from src.client.services_client_sdr import get_sdr_blacklist_words, update_sdr_blacklist_words
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
)


@use_app_context
def test_update_sdr_blacklist_words():
    client = basic_client()
    sdr = basic_client_sdr(client)
    blacklist_words = ["word1", "word2", "word3"]

    assert sdr.blacklisted_words == None
    update_sdr_blacklist_words(sdr.id, blacklist_words)
    assert sdr.blacklisted_words == blacklist_words


@use_app_context
def test_get_sdr_blacklist_words():
    client = basic_client()
    sdr = basic_client_sdr(client)
    blacklist_words = ["word1", "word2", "word3"]

    assert sdr.blacklisted_words == None
    update_sdr_blacklist_words(sdr.id, blacklist_words)
    assert sdr.blacklisted_words == blacklist_words

    assert get_sdr_blacklist_words(sdr.id) == blacklist_words
