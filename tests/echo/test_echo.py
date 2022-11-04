from app import db, app
from test_utils import test_app
from model_import import Echo
import pytest
from config import TestingConfig
from decorators import use_app_context


def test_echo(test_app):
    with test_app.app_context():
        e: Echo = Echo()
        print(e.id)
        db.session.add(e)
        db.session.commit()
        assert e is not None


@use_app_context
def test_echo_route():
    response = app.test_client().get("/echo/")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"
