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
    ProspectOverallStatus,
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
    StackRankedMessageGenerationConfiguration,
    ProspectEmail,
    ProspectEmailStatus,
    ProspectEmailOutreachStatus,
    GeneratedMessageType,
    LinkedinConversationEntry,
    IScraperPayloadCache,
    IScraperPayloadType,
    GeneratedMessageJobQueue,
)
from src.daily_notifications.models import (
    DailyNotification,
    NotificationStatus,
    NotificationType,
)
from typing import Optional
from datetime import datetime


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
        clear_all_entities(IScraperPayloadCache)
        clear_all_entities(LinkedinConversationEntry)
        clear_all_entities(GeneratedMessageEditRecord)
        clear_all_entities(ProspectUploadBatch)
        clear_all_entities(GeneratedMessageJob)
        clear_all_entities(GeneratedMessageJobQueue)
        clear_all_entities(ResponseConfiguration)
        clear_all_entities(GeneratedMessageFeedback)
        clear_all_entities(OutboundCampaign)
        clear_all_entities(SightOnboarding)
        clear_all_entities(ProspectEmailStatusRecords)
        clear_all_entities(ProspectEmail)
        clear_all_entities(SalesEngagementInteractionSS)
        clear_all_entities(SalesEngagementInteractionRaw)
        clear_all_entities(EmailSchema)
        clear_all_entities(AdversaryTrainingPoint)
        clear_all_entities(GeneratedMessage)
        clear_all_entities(GeneratedMessageCTA)
        clear_all_entities(ResearchPoints)
        clear_all_entities(ResearchPayload)
        clear_all_entities(ProspectStatusRecords)
        clear_all_entities(PhantomBusterConfig)
        clear_all_entities(DailyNotification)
        clear_all_entities(ProspectNote)
        clear_all_entities(ProspectUploads)
        clear_all_entities(ProspectUploadsRawCSV)
        clear_all_entities(Prospect)
        clear_all_entities(GNLPModel)
        clear_all_entities(GNLPModelFineTuneJobs)
        clear_all_entities(StackRankedMessageGenerationConfiguration)
        clear_all_entities(ClientArchetype)
        clear_all_entities(ClientSDR)
        clear_all_entities(Client)
        clear_all_entities(Editor)

    return app


def get_login_token():
    return "TEST_AUTH_TOKEN"


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


def basic_archetype(client: Client, client_sdr: Optional[ClientSDR] = None) -> ClientArchetype:
    client_sdr_id = None if client_sdr is None else client_sdr.id
    a = ClientArchetype(
        client_id=client.id,
        client_sdr_id=client_sdr_id,
        archetype="Testing archetype"
    )
    db.session.add(a)
    db.session.commit()
    return a


def basic_prospect(
    client: Client,
    archetype: ClientArchetype,
    client_sdr: ClientSDR = None,
    email: Optional[str] = "test@email.com",
    li_conversation_thread_id: Optional[str] = "",
    status=ProspectStatus.PROSPECTED,
    overall_status=ProspectOverallStatus.PROSPECTED,
    full_name: Optional[str] = "Testing Testasara",
    title: Optional[str] = "Testing Director",
    company: Optional[str] = "",
) -> Prospect:
    client_sdr_id = None
    if client_sdr:
        client_sdr_id = client_sdr.id
    p = Prospect(
        company=company,
        client_id=client.id,
        archetype_id=archetype.id,
        full_name=full_name,
        title=title,
        status=status,
        overall_status=overall_status,
        client_sdr_id=client_sdr_id,
        email=email,
        li_conversation_thread_id=li_conversation_thread_id,
    )
    db.session.add(p)
    db.session.commit()
    return p


def basic_client_sdr(client: Client) -> ClientSDR:
    sdr = ClientSDR(
        client_id=client.id,
        name="Test SDR",
        email="test@test.com",
        auth_token="TEST_AUTH_TOKEN",
    )
    db.session.add(sdr)
    db.session.commit()
    return sdr


def basic_daily_notification(
    client_sdr: ClientSDR,
    status: NotificationStatus,
    type: NotificationType = "UNKNOWN",
    prospect_id: int = -1,
) -> DailyNotification:
    dnot = DailyNotification(
        client_sdr_id=client_sdr.id,
        type=type,
        status=status,
        title="Testing title",
        description="Testing description",
        due_date=datetime.now(),
        prospect_id=prospect_id,
    )
    db.session.add(dnot)
    db.session.commit()
    return dnot


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


def basic_outbound_campaign(
    prospect_ids: list[int],
    campaign_type: GeneratedMessageType,
    client_archetype: ClientArchetype,
    client_sdr: ClientSDR,
    name: str = "test_campaign",
):
    from model_import import OutboundCampaignStatus
    from datetime import datetime

    o = OutboundCampaign(
        name=name,
        prospect_ids=prospect_ids,
        campaign_type=campaign_type,
        client_archetype_id=client_archetype.id,
        client_sdr_id=client_sdr.id,
        campaign_start_date=datetime.now(),
        campaign_end_date=datetime.now(),
        status=OutboundCampaignStatus.READY_TO_SEND,
    )
    db.session.add(o)
    db.session.commit()
    return o


def basic_generated_message_cta(archetype: ClientArchetype):
    from model_import import GeneratedMessageCTA

    g = GeneratedMessageCTA(
        archetype_id=archetype.id, text_value="test_cta", active=True
    )
    db.session.add(g)
    db.session.commit()
    return g


def basic_generated_message(prospect: Prospect, gnlp_model: GNLPModel, message_cta: Optional[GeneratedMessageCTA] = None):
    from model_import import (
        GeneratedMessage,
        GeneratedMessageStatus,
        GeneratedMessageType,
    )

    message_cta_id = None if message_cta is None else message_cta.id
    g = GeneratedMessage(
        prospect_id=prospect.id,
        gnlp_model_id=gnlp_model.id,
        research_points=[],
        prompt="",
        completion="this is a test",
        message_status=GeneratedMessageStatus.DRAFT,
        message_type=GeneratedMessageType.LINKEDIN,
        message_cta=message_cta_id
    )
    db.session.add(g)
    db.session.commit()
    return g


def basic_generated_message_cta_with_text(archetype: ClientArchetype, text_value: str):
    from model_import import (
        GeneratedMessageCTA,
    )

    g_cta = GeneratedMessageCTA(
        archetype_id=archetype.id,
        text_value=text_value or "test_cta",
        active=True,
    )
    db.session.add(g_cta)
    db.session.commit()
    return g_cta


def basic_prospect_email(
    prospect: Prospect,
    email_status: ProspectEmailStatus = ProspectEmailStatus.DRAFT,
    outreach_status: ProspectEmailOutreachStatus = ProspectEmailOutreachStatus.UNKNOWN,
) -> ProspectEmail:

    p = ProspectEmail(
        prospect_id=prospect.id,
        email_status=email_status,
        outreach_status=outreach_status,
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
        client_id=client.id,
        client_sdr_id=client_sdr.id,
        pb_type=PhantomBusterType.INBOX_SCRAPER,
        phantom_uuid="1",
    )

    outboundp = PhantomBusterConfig(
        client_id=client.id,
        client_sdr_id=client_sdr.id,
        pb_type=PhantomBusterType.OUTBOUND_ENGINE,
        phantom_uuid="2",
    )

    db.session.add_all([inboxp, outboundp])
    db.session.commit()
    return inboxp, outboundp


def basic_prospect_uploads_raw_csv(
    client: Client, client_sdr: ClientSDR, client_archetype: ClientArchetype
):
    from model_import import ProspectUploadsRawCSV

    p = ProspectUploadsRawCSV(
        client_id=client.id,
        client_archetype_id=client_archetype.id,
        client_sdr_id=client_sdr.id,
        csv_data={"test": "test"},
        csv_data_hash="1234567890",
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
        csv_row_data={"linkedin_url": "https://www.linkedin.com/in/davidmwei"},
        csv_row_hash="1234567890",
        upload_attempts=0,
        status=ProspectUploadsStatus.UPLOAD_NOT_STARTED,
    )
    db.session.add(pu)
    db.session.commit()
    return pu


def basic_sei_raw(
    client: Client,
    client_sdr: ClientSDR,
    csv_data: Optional[list[dict]] = [{"test": "test"}],
):
    from model_import import (
        SalesEngagementInteractionRaw,
        SalesEngagementInteractionSource,
    )

    s = SalesEngagementInteractionRaw(
        client_id=client.id,
        client_sdr_id=client_sdr.id,
        csv_data=csv_data,
        csv_data_hash="1234567890",
        source=SalesEngagementInteractionSource.OUTREACH,
        sequence_name="test-sequence",
    )
    db.session.add(s)
    db.session.commit()
    return s


def basic_sei_ss(
    client: Client, client_sdr: ClientSDR, sei_raw: SalesEngagementInteractionRaw
):
    from model_import import SalesEngagementInteractionSS

    s = SalesEngagementInteractionSS(
        client_id=client.id,
        client_sdr_id=client_sdr.id,
        sales_engagement_interaction_raw_id=sei_raw.id,
        ss_status_data=[{"test": "test"}],
    )
    db.session.add(s)
    db.session.commit()
    return s


def basic_linkedin_conversation_entry(
    conversation_url: str = "test_convo_url",
    author: str = "test_author",
    first_name: str = "test_first_name",
    last_name: str = "test_last_name",
    date: datetime = datetime.now(),
    profile_url: str = "test_profile_url",
    headline: str = "test_headline",
    img_url: str = "test_img_url",
    connection_degree: str = "test_connection_degree",
    li_url: str = "test_li_url",
    message: str = "test_message",
    entry_processed: bool = False,
) -> LinkedinConversationEntry:

    entry = LinkedinConversationEntry(
        conversation_url=conversation_url,
        author=author,
        first_name=first_name,
        last_name=last_name,
        date=date,
        profile_url=profile_url,
        headline=headline,
        img_url=img_url,
        connection_degree=connection_degree,
        li_url=li_url,
        message=message,
        entry_processed=entry_processed,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


EXAMPLE_PAYLOAD_PERSONAL = {
    "position_groups": [
        {
            "company": {
                "name": "Test",
                "url": "https://www.linkedin.com/company/test_company"
            }
        },
    ]
}

EXAMPLE_PAYLOAD_COMPANY = {
    "details": {
        "name": "Fake Company TEST"
    }
}

def basic_iscraper_payload_cache(
    linkedin_url: str = "test_linkedin_url",
    payload: dict = EXAMPLE_PAYLOAD_PERSONAL,
    payload_type: IScraperPayloadType = IScraperPayloadType.PERSONAL,
    is_company_payload: bool = False,
) -> IScraperPayloadCache:
    if is_company_payload:
        payload = EXAMPLE_PAYLOAD_COMPANY
        payload_type = IScraperPayloadType.COMPANY
    cache = IScraperPayloadCache(
        linkedin_url=linkedin_url,
        payload=payload,
        payload_type=payload_type,
    )
    db.session.add(cache)
    db.session.commit()
    return cache


def clear_all_entities(SQLAlchemyObject):
    echos = SQLAlchemyObject.query.all()
    for e in echos:
        db.session.delete(e)
    db.session.commit()


def test_simple_test():
    assert True
