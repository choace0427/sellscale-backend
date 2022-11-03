from src.utils.random_string import *
from app import db
import mock


def test_generate_secure_random_hex():
    assert len(generate_secure_random_hex(10)) == 10


def test_generate_random_alphabet():
    assert len(generate_random_alphabet(10)) == 10


def test_generate_random_alphanumeric():
    assert len(generate_random_alphanumeric(10)) == 10


def test_generate_random_file_path():
    assert len(generate_random_file_path()) > 5
