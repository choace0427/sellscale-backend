import pytest
from app import db
from config import TestingConfig
from model_import import (
    Client,
    ClientArchetype,
    Echo,
    Prospect,
    GNLPModel,
    ClientSDR,
    EmailSchema,
    GeneratedMessage,
    ProspectEmail,
    GeneratedMessageCTA,
    ResearchPayload,
    ResearchPoints,
)


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
        clear_all_entities(ProspectEmail)
        clear_all_entities(EmailSchema)
        for p in Prospect.query.all():
            prospect: Prospect = p
            prospect.approved_outreach_message_id = None
            db.session.add(prospect)
            db.session.commit()
        clear_all_entities(GeneratedMessage)
        clear_all_entities(GeneratedMessageCTA)
        clear_all_entities(ResearchPoints)
        clear_all_entities(ResearchPayload)
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


def basic_archetype(client: Client) -> ClientArchetype:
    a = ClientArchetype(client_id=client.id, archetype="Testing archetype")
    db.session.add(a)
    db.session.commit()
    return a


def basic_prospect(client: Client, archetype: ClientArchetype):
    p = Prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        full_name="Testing Testasara",
        title="Testing Director",
    )
    db.session.add(p)
    db.session.commit()
    return p


def basic_gnlp_model(archetype: ClientArchetype):
    from src.ml.models import ModelProvider, GNLPModelType

    g = GNLPModel(
        model_provider=ModelProvider.OPENAI_GPT3,
        model_type=GNLPModelType.OUTREACH,
        model_description="test_model",
        model_uuid="1234567890",
        archetype_id=archetype.id,
    )
    db.session.add(g)
    db.session.commit()
    return g


def basic_generated_message(prospect: Prospect, gnlp_model: GNLPModel):
    from model_import import (
        GeneratedMessage,
        GeneratedMessageStatus,
        GeneratedMessageType,
    )

    g = GeneratedMessage(
        prospect_id=prospect.id,
        gnlp_model_id=gnlp_model.id,
        research_points=[],
        prompt="",
        completion="this is a test",
        message_status=GeneratedMessageStatus.DRAFT,
        message_type=GeneratedMessageType.LINKEDIN,
    )
    db.session.add(g)
    db.session.commit()
    return g


def clear_all_entities(SQLAlchemyObject):
    echos = SQLAlchemyObject.query.all()
    for e in echos:
        db.session.delete(e)
    db.session.commit()


def test_simple_test():
    assert True
