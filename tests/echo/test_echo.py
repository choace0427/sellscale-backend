from app import db
from test_utils import test_app
from model_import import Echo
import pytest
from config import TestingConfig


def test_echo(test_app):
    with test_app.app_context():
        e: Echo = Echo()
        print(e.id)
        db.session.add(e)
        db.session.commit()
        assert e is not None
