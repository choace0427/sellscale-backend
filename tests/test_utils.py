import pytest
from app import db
from config import TestingConfig
from model_import import (
    Client,
    ClientArchetype,
    Echo,
    Prospect,
    ProspectUploadsRawCSV,
    ProspectUploads,
    GNLPModel,
    ClientSDR,
    EmailSchema,
    GeneratedMessage,
    ProspectEmailStatusRecords,
    ProspectEmail,
    GeneratedMessageCTA,
    ResearchPayload,
    ResearchPoints,
    ProspectStatus,
    GNLPModelFineTuneJobs,
    ProspectStatusRecords,
    PhantomBusterConfig,
    ProspectUploadBatch,
    ProspectNote,
    OutboundCampaign,
    GeneratedMessageFeedback,
    GeneratedMessageJob,
    ResponseConfiguration,
    SightOnboarding,
    AdversaryTrainingPoint,
    Editor,
    GeneratedMessageEditRecord,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSS,
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
        for p in Prospect.query.all():
            prospect: Prospect = p
            prospect.approved_outreach_message_id = None
            prospect.approved_prospect_email_id = None
            db.session.add(prospect)
            db.session.commit()
        clear_all_entities(SalesEngagementInteractionSS)
        clear_all_entities(SalesEngagementInteractionRaw)
        clear_all_entities(GeneratedMessageEditRecord)
        clear_all_entities(ProspectUploadBatch)
        clear_all_entities(GeneratedMessageJob)
        clear_all_entities(ResponseConfiguration)
        clear_all_entities(GeneratedMessageFeedback)
        clear_all_entities(OutboundCampaign)
        clear_all_entities(SightOnboarding)
        clear_all_entities(ProspectEmailStatusRecords)
        clear_all_entities(ProspectEmail)
        clear_all_entities(EmailSchema)
        clear_all_entities(AdversaryTrainingPoint)
        clear_all_entities(GeneratedMessage)
        clear_all_entities(GeneratedMessageCTA)
        clear_all_entities(ResearchPoints)
        clear_all_entities(ResearchPayload)
        clear_all_entities(ProspectStatusRecords)
        clear_all_entities(PhantomBusterConfig)
        clear_all_entities(ProspectNote)
        clear_all_entities(ProspectUploads)
        clear_all_entities(ProspectUploadsRawCSV)
        clear_all_entities(Prospect)
        clear_all_entities(GNLPModel)
        clear_all_entities(GNLPModelFineTuneJobs)
        clear_all_entities(ClientArchetype)
        clear_all_entities(ClientSDR)
        clear_all_entities(Client)
        clear_all_entities(Editor)

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


def basic_editor() -> Editor:
    e = Editor(
        name="Testing Editor",
        email="email",
        editor_type="SELLSCALE_ADMIN",
    )
    db.session.add(e)
    db.session.commit()
    return e


def basic_archetype(client: Client) -> ClientArchetype:
    a = ClientArchetype(client_id=client.id, archetype="Testing archetype")
    db.session.add(a)
    db.session.commit()
    return a


def basic_prospect(client: Client, archetype: ClientArchetype, client_sdr: ClientSDR = None):
    client_sdr_id = None
    if client_sdr:
        client_sdr_id = client_sdr.id
    p = Prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        full_name="Testing Testasara",
        title="Testing Director",
        status=ProspectStatus.PROSPECTED,
        client_sdr_id=client_sdr_id,
    )
    db.session.add(p)
    db.session.commit()
    return p


def basic_client_sdr(client: Client) -> ClientSDR:
    sdr = ClientSDR(client_id=client.id, name="Test SDR", email="test@test.com")
    db.session.add(sdr)
    db.session.commit()
    return sdr


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


def basic_generated_message_cta(archetype: ClientArchetype):
    from model_import import GeneratedMessageCTA

    g = GeneratedMessageCTA(
        archetype_id=archetype.id, text_value="test_cta", active=True
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


def basic_generated_message_cta_with_text(archetype: ClientArchetype, text_value: str):
    from model_import import (
        GeneratedMessageCTA,
    )

    g_cta = GeneratedMessageCTA(
        archetype_id = archetype.id,
        text_value=text_value or "test_cta",
        active=True,
    )
    db.session.add(g_cta)
    db.session.commit()
    return g_cta


def basic_email_schema(archetype: ClientArchetype):
    from model_import import EmailSchema

    e = EmailSchema(
        name="Test Schema",
        client_archetype_id=archetype.id,
    )
    db.session.add(e)
    db.session.commit()
    return e


def basic_prospect_email(
    prospect: Prospect,
    email_schema: EmailSchema,
) -> ProspectEmail:
    from model_import import ProspectEmail
    from src.email_outbound.models import ProspectEmailStatus

    p = ProspectEmail(
        email_schema_id=email_schema.id,
        prospect_id=prospect.id,
        email_status=ProspectEmailStatus.DRAFT,
    )
    db.session.add(p)
    db.session.commit()
    return p


def basic_research_payload(prospect: Prospect):
    from model_import import ResearchPayload

    r = ResearchPayload(
        prospect_id=prospect.id,
        research_type="LINKEDIN_ISCRAPER",
        payload="test",
    )
    db.session.add(r)
    db.session.commit()
    return r


def basic_research_point(research_payload: ResearchPayload):
    from model_import import ResearchPoints

    r = ResearchPoints(
        research_payload_id=research_payload.id,
        research_point_type="RECENT_RECOMMENDATIONS",
        value="this is a test",
    )
    db.session.add(r)
    db.session.commit()
    return r


def basic_phantom_buster_configs(client: Client, client_sdr: ClientSDR):
    from model_import import PhantomBusterConfig, PhantomBusterType

    inboxp = PhantomBusterConfig(
        client_id = client.id,
        client_sdr_id = client_sdr.id,
        pb_type = PhantomBusterType.INBOX_SCRAPER,
        phantom_uuid = "1"
    )

    outboundp = PhantomBusterConfig(
        client_id = client.id,
        client_sdr_id = client_sdr.id,
        pb_type = PhantomBusterType.OUTBOUND_ENGINE,
        phantom_uuid = "2"
    )

    db.session.add_all([inboxp, outboundp])
    db.session.commit()
    return inboxp, outboundp


def basic_prospect_uploads_raw_csv(client: Client, client_sdr: ClientSDR, client_archetype: ClientArchetype):
    from model_import import ProspectUploadsRawCSV

    p = ProspectUploadsRawCSV(
        client_id=client.id,
        client_archetype_id=client_archetype.id,
        client_sdr_id=client_sdr.id,
        csv_data = {"test": "test"},
        csv_data_hash = "1234567890"
    )
    db.session.add(p)
    db.session.commit()
    return p


def basic_prospect_uploads(
    client: Client,
    client_sdr: ClientSDR,
    client_archetype: ClientArchetype,
    prospect_uploads_raw_csv: ProspectUploadsRawCSV,
):
    from model_import import ProspectUploads, ProspectUploadsStatus

    pu = ProspectUploads(
        client_id=client.id,
        client_archetype_id=client_archetype.id,
        client_sdr_id=client_sdr.id,
        prospect_uploads_raw_csv_id=prospect_uploads_raw_csv.id,
        csv_row_data = {"linkedin_url": "https://www.linkedin.com/in/davidmwei"},
        csv_row_hash = "1234567890",
        upload_attempts = 0,
        status = ProspectUploadsStatus.UPLOAD_NOT_STARTED,
    )
    db.session.add(pu)
    db.session.commit()
    return pu


def clear_all_entities(SQLAlchemyObject):
    echos = SQLAlchemyObject.query.all()
    for e in echos:
        db.session.delete(e)
    db.session.commit()


def test_simple_test():
    assert True
