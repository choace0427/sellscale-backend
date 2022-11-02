import pytest
from app import db
from config import TestingConfig
from model_import import Client, ClientArchetype, Echo, Prospect, GNLPModel, ClientSDR


@pytest.fixture
def test_app():
    from app import app

    app.config.from_object(TestingConfig)
    sql_url = app.config["SQLALCHEMY_DATABASE_URI"]
    if "/testing" not in sql_url:
        raise Exception(
            "You are not in the correct environment! Switch to TESTING environment and ensure that /testing database exists locally."
        )

    with app.app_context():
        clear_all_entities(Echo)
        clear_all_entities(Prospect)
        clear_all_entities(GNLPModel)
        clear_all_entities(ClientSDR)
        clear_all_entities(ClientArchetype)
        clear_all_entities(Client)

    return app


def basic_client() -> Client:
    c = Client(
        company="Testing Company",
        contact_name="Testing@test.com",
        contact_email="Testing123@test.com",
    )
    db.session.add(c)
    db.session.commit()
    return c


def basic_archetype(client: Client):
    a = ClientArchetype(client_id=client.id, archetype="Testing archetype")
    db.session.add(a)
    db.session.commit()
    return a


def clear_all_entities(SQLAlchemyObject):
    echos = SQLAlchemyObject.query.all()
    for e in echos:
        db.session.delete(e)
    db.session.commit()


def test_simple_test():
    assert True
