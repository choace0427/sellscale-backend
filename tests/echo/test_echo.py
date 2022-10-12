from model_import import Echo
from app import db


def test_simple_test():
    assert True


def test_echo():
    e: Echo = Echo()
    db.session.add(e)
    db.session.commit()
    assert e is not None
