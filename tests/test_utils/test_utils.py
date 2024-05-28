import json
import os
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
    ProspectStatusRecords,
    PhantomBusterConfig,
    DemoFeedback,
    ProspectNote,
    OutboundCampaign,
    GeneratedMessageFeedback,
    GeneratedMessageJob,
    GeneratedMessageAutoBump,
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
    GeneratedMessageJobStatus,
    ClientPod,
    BumpFramework,
    StackRankedMessageGenerationConfiguration,
    ConfigurationType,
    EngagementFeedItem,
    AccountResearchPoints,
    PersonaSplitRequest,
    PersonaSplitRequestTask,
    PhantomBusterPayload,
    TextGeneration,
)
from src.automation.models import (
    PhantomBusterSalesNavigatorConfig,
    PhantomBusterSalesNavigatorLaunch,
    SalesNavigatorLaunchStatus,
)
from src.bump_framework.models import BumpLength, JunctionBumpFrameworkClientArchetype
from src.client.models import SLASchedule
from src.client.sdr.email.models import EmailType, SDREmailBank, SDREmailSendSchedule
from src.daily_notifications.models import (
    DailyNotification,
    NotificationStatus,
    NotificationType,
)
from typing import Optional
from datetime import datetime, time, timedelta
from src.email_scheduling.models import EmailMessagingSchedule

from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.prospecting.icp_score.models import ICPScoringRuleset
from src.utils.datetime.dateutils import get_current_monday_friday

ENV = os.environ.get("FLASK_ENV")


@pytest.fixture
def test_app():
    from app import app

    app.config.from_object(TestingConfig)
    sql_url = app.config["SQLALCHEMY_DATABASE_URI"]
    if (ENV != "testing") or ("production" in sql_url):
        raise Exception(
            "You are not in the correct environment! Switch to TESTING environment and ensure that a database exists locally."
        )

    # if "/testing" not in sql_url:
    #     raise Exception(
    #         "You are not in the correct environment! Switch to TESTING environment and ensure that /testing database exists locally."
    #     )

    with app.app_context():
        clear_all_entities(TextGeneration)
        clear_all_entities(EmailMessagingSchedule)
        clear_all_entities(SDREmailSendSchedule)
        clear_all_entities(SDREmailBank)
        clear_all_entities(JunctionBumpFrameworkClientArchetype)
        clear_all_entities(EngagementFeedItem)
        clear_all_entities(Echo)
        for p in Prospect.query.all():
            prospect: Prospect = p
            prospect.approved_outreach_message_id = None
            prospect.approved_prospect_email_id = None
            db.session.add(prospect)
            db.session.commit()
        clear_all_entities(PhantomBusterPayload)
        clear_all_entities(SLASchedule)
        clear_all_entities(IScraperPayloadCache)
        clear_all_entities(PersonaSplitRequestTask)
        clear_all_entities(PersonaSplitRequest)
        clear_all_entities(LinkedinConversationEntry)
        clear_all_entities(GeneratedMessageAutoBump)
        clear_all_entities(BumpFramework)
        clear_all_entities(EmailSequenceStep)
        clear_all_entities(EmailSubjectLineTemplate)
        clear_all_entities(GeneratedMessageEditRecord)
        clear_all_entities(GeneratedMessageJob)
        clear_all_entities(GeneratedMessageJobQueue)
        clear_all_entities(ResponseConfiguration)
        clear_all_entities(GeneratedMessageFeedback)
        clear_all_entities(SightOnboarding)
        clear_all_entities(ProspectEmailStatusRecords)
        clear_all_entities(ProspectEmail)
        clear_all_entities(AccountResearchPoints)
        clear_all_entities(SalesEngagementInteractionSS)
        clear_all_entities(SalesEngagementInteractionRaw)
        clear_all_entities(EmailSchema)
        clear_all_entities(AdversaryTrainingPoint)
        clear_all_entities(GeneratedMessage)
        clear_all_entities(GeneratedMessageCTA)
        clear_all_entities(OutboundCampaign)
        clear_all_entities(ResearchPoints)
        clear_all_entities(ResearchPayload)
        clear_all_entities(ProspectStatusRecords)
        clear_all_entities(PhantomBusterConfig)
        clear_all_entities(DailyNotification)
        clear_all_entities(ProspectNote)
        clear_all_entities(ProspectUploads)
        clear_all_entities(ProspectUploadsRawCSV)
        clear_all_entities(DemoFeedback)
        clear_all_entities(Prospect)
        clear_all_entities(StackRankedMessageGenerationConfiguration)
        clear_all_entities(ICPScoringRuleset)
        clear_all_entities(ClientArchetype)
        clear_all_entities(PhantomBusterSalesNavigatorLaunch)
        clear_all_entities(PhantomBusterSalesNavigatorConfig)
        clear_all_entities(ClientSDR)
        clear_all_entities(ClientPod)
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


def basic_archetype(
    client: Client, client_sdr: Optional[ClientSDR] = None
) -> ClientArchetype:
    client_sdr_id = None if client_sdr is None else client_sdr.id
    a = ClientArchetype(
        client_id=client.id,
        client_sdr_id=client_sdr_id,
        archetype="Testing archetype",
        active=True,
        li_bump_amount=0,
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
        active=True,
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


def basic_outbound_campaign(
    prospect_ids: list[int],
    campaign_type: GeneratedMessageType,
    client_archetype: ClientArchetype,
    client_sdr: ClientSDR,
    name: str = "test_campaign",
):
    from model_import import OutboundCampaignStatus
    from datetime import datetime

    today = datetime.today()
    days_until_next_monday = (7 - today.weekday()) % 7
    next_monday = today + timedelta(days=days_until_next_monday)
    next_sunday = next_monday + timedelta(days=6)

    o = OutboundCampaign(
        name=name,
        prospect_ids=prospect_ids,
        campaign_type=campaign_type,
        client_archetype_id=client_archetype.id,
        client_sdr_id=client_sdr.id,
        campaign_start_date=next_monday,
        campaign_end_date=next_sunday,
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


def basic_generated_message(
    prospect: Prospect,
    message_cta: Optional[GeneratedMessageCTA] = None,
    campaign: Optional[OutboundCampaign] = None,
):
    from model_import import (
        GeneratedMessage,
        GeneratedMessageStatus,
        GeneratedMessageType,
    )

    message_cta_id = None if message_cta is None else message_cta.id
    g = GeneratedMessage(
        prospect_id=prospect.id,
        outbound_campaign_id=campaign.id if campaign else None,
        research_points=[],
        prompt="",
        completion="this is a test",
        message_status=GeneratedMessageStatus.DRAFT,
        message_type=GeneratedMessageType.LINKEDIN,
        message_cta=message_cta_id,
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

    # Updated approved_prospect_email_id
    prospect.approved_prospect_email_id = p.id
    db.session.add(prospect)
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
        data={"linkedin_url": "https://www.linkedin.com/in/davidmwei"},
        data_hash="1234567890",
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


def basic_generated_message_job_queue(
    prospect: Prospect,
    outbound_campaign: OutboundCampaign,
    status: GeneratedMessageJobStatus,
    error_message: Optional[str] = "test_error_message",
    attempts: Optional[str] = 0,
):
    job = GeneratedMessageJobQueue(
        prospect_id=prospect.id,
        outbound_campaign_id=outbound_campaign.id,
        status=status,
        error_message=error_message,
        attempts=attempts,
    )
    db.session.add(job)
    db.session.commit()
    return job


def basic_stack_ranked_message_generation_config(
    instruction: str = "test_instruction",
    computed_prompt: str = "test_computed_prompt",
    configuration_type: ConfigurationType = ConfigurationType.DEFAULT,
    generated_message_type: GeneratedMessageType = GeneratedMessageType.LINKEDIN,
    research_point_types: Optional[list[str]] = None,
    active: Optional[bool] = True,
    always_enable: Optional[bool] = False,
    name: Optional[str] = "test_name",
    client_id: Optional[int] = None,
    archetype_id: Optional[int] = None,
    priority: Optional[int] = None,
):
    config = StackRankedMessageGenerationConfiguration(
        configuration_type=configuration_type,
        generated_message_type=generated_message_type,
        research_point_types=research_point_types,
        instruction=instruction,
        computed_prompt=computed_prompt,
        active=active,
        always_enable=always_enable,
        name=name,
        client_id=client_id,
        archetype_id=archetype_id,
        priority=priority,
    )
    db.session.add(config)
    db.session.commit()
    return config


EXAMPLE_PAYLOAD_PERSONAL = {
    "position_groups": [
        {
            "company": {
                "name": "Test",
                "url": "https://www.linkedin.com/company/test_company",
            }
        },
    ]
}

EXAMPLE_PAYLOAD_COMPANY = {"details": {"name": "Fake Company Mock"}}


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
        payload=json.dumps(payload),
        payload_type=payload_type,
    )
    db.session.add(cache)
    db.session.commit()
    return cache


def basic_engagement_feed_item(
    client_sdr_id: int,
    prospect_id: int,
    channel_type: str,
    engagement_type: str,
    viewed: bool = False,
    engagement_metadata: Optional[dict] = None,
):
    new_item = EngagementFeedItem(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        channel_type=channel_type,
        engagement_type=engagement_type,
        viewed=viewed,
        engagement_metadata=engagement_metadata,
    )
    db.session.add(new_item)
    db.session.commit()

    return new_item.id


def basic_bump_framework(
    client_sdr: ClientSDR,
    client_archetype: ClientArchetype = None,
    title: str = "test-title",
    description: str = "test-description",
    length: BumpLength = BumpLength.MEDIUM,
    active: bool = True,
    overall_status: ProspectOverallStatus = ProspectOverallStatus.BUMPED,
    default: bool = False,
    use_account_research: bool = True,
):
    from model_import import BumpFramework

    bump_framework = BumpFramework(
        client_sdr_id=client_sdr.id,
        client_archetype_id=client_archetype.id if client_archetype else None,
        title=title,
        description=description,
        bump_length=length,
        active=active,
        overall_status=overall_status,
        default=default,
        use_account_research=use_account_research,
    )
    db.session.add(bump_framework)
    db.session.commit()

    return bump_framework


# Email Bump Framework
def basic_email_sequence_step(
    client_sdr: ClientSDR,
    client_archetype: ClientArchetype,
    title: str = "test-title",
    email_blocks: list[str] = [],
    active: bool = True,
    overall_status: ProspectOverallStatus = ProspectOverallStatus.ACTIVE_CONVO,
    substatus: str = "ACTIVE_CONVO_NEXT_STEPS",
    bumped_count: int = 1,
    default: bool = False,
    sellscale_default_generated: bool = False,
    template: str = None,
    sequence_delay_days: int = None,
):
    from model_import import EmailSequenceStep

    email_sequence_step = EmailSequenceStep(
        client_sdr_id=client_sdr.id,
        client_archetype_id=client_archetype.id,
        title=title,
        email_blocks=email_blocks,
        overall_status=overall_status,
        substatus=substatus,
        bumped_count=bumped_count,
        active=active,
        default=default,
        sellscale_default_generated=sellscale_default_generated,
        template=template,
        sequence_delay_days=sequence_delay_days,
    )
    db.session.add(email_sequence_step)
    db.session.commit()

    return email_sequence_step


def basic_email_subject_line_template(
    client_sdr: ClientSDR,
    client_archetype: ClientArchetype,
    subject_line: str = "test-subject-line",
    active: bool = True,
    times_used: int = 0,
    times_accepted: int = 0,
    sellscale_generated: bool = False,
):
    from model_import import EmailSubjectLineTemplate

    email_subject_line_template = EmailSubjectLineTemplate(
        client_sdr_id=client_sdr.id,
        client_archetype_id=client_archetype.id,
        subject_line=subject_line,
        active=active,
        times_used=times_used,
        times_accepted=times_accepted,
        sellscale_generated=sellscale_generated,
    )
    db.session.add(email_subject_line_template)
    db.session.commit()

    return email_subject_line_template


def basic_generated_message_autobump(
    prospect: Prospect,
    client_sdr: ClientSDR,
    bump_framework: BumpFramework = None,
    message: str = "test-message",
    account_research_points: list[str] = None,
):
    autobump = GeneratedMessageAutoBump(
        prospect_id=prospect.id,
        client_sdr_id=client_sdr.id,
        bump_framework_id=bump_framework.id if bump_framework else None,
        message=message,
        account_research_points=account_research_points,
        bump_framework_title=bump_framework.title if bump_framework else None,
        bump_framework_description=(
            bump_framework.description if bump_framework else None
        ),
        bump_framework_length=bump_framework.bump_length if bump_framework else None,
    )
    db.session.add(autobump)
    db.session.commit()

    return autobump


def basic_pb_sn_config(
    common_pool: bool = True,
    phantom_name: str = "test_phantom_name",
    phantom_uuid: str = "test_phantom_uuid",
    linkedin_session_cookie: str = "test_linkedin_session_cookie",
    daily_trigger_count: int = 0,
    daily_prospect_count: int = 0,
    in_use: bool = False,
    client: Client = None,
    client_sdr: ClientSDR = None,
):
    phantom = PhantomBusterSalesNavigatorConfig(
        client_id=client.id if client else None,
        client_sdr_id=client_sdr.id if client_sdr else None,
        common_pool=common_pool,
        phantom_name=phantom_name,
        phantom_uuid=phantom_uuid,
        linkedin_session_cookie=linkedin_session_cookie,
        daily_trigger_count=daily_trigger_count,
        daily_prospect_count=daily_prospect_count,
        in_use=in_use,
    )
    db.session.add(phantom)
    db.session.commit()

    return phantom


def basic_pb_sn_launch(
    phantom: PhantomBusterSalesNavigatorConfig,
    client_sdr: ClientSDR,
    sales_navigator_url: str = "test_sales_navigator_url",
    scrape_count: int = 0,
    status: SalesNavigatorLaunchStatus = SalesNavigatorLaunchStatus.QUEUED,
    pb_container_id: str = None,
    result_raw: list[dict] = None,
):
    launch = PhantomBusterSalesNavigatorLaunch(
        sales_navigator_config_id=phantom.id,
        client_sdr_id=client_sdr.id,
        sales_navigator_url=sales_navigator_url,
        scrape_count=scrape_count,
        status=status,
        pb_container_id=pb_container_id,
        result_raw=result_raw,
    )
    db.session.add(launch)
    db.session.commit()

    return launch


def basic_demo_feedback(
    client: Client,
    client_sdr: ClientSDR,
    prospect: Prospect,
    status: str = "test_status",
    rating: str = "test_rating",
    feedback: str = "test_feedback",
    demo_date: datetime = datetime.now(),
    next_demo_date: datetime = datetime.now() + timedelta(days=1),
) -> DemoFeedback:
    df: DemoFeedback = DemoFeedback(
        client_id=client.id,
        client_sdr_id=client_sdr.id,
        prospect_id=prospect.id,
        status=status,
        rating=rating,
        feedback=feedback,
        demo_date=demo_date,
        next_demo_date=next_demo_date,
    )
    db.session.add(df)
    db.session.commit()

    return df


def basic_sla_schedule(
    client_sdr: ClientSDR,
    start_date: datetime = datetime.now(),
    linkedin_volume: int = 0,
    linkedin_special_notes: str = "test_linkedin_special_notes",
    email_volume: int = 0,
    email_special_notes: str = "test_email_special_notes",
    week: int = 0,
) -> SLASchedule:
    # Get the monday of the start date's given week
    start_date, end_date = get_current_monday_friday(start_date)

    schedule: SLASchedule = SLASchedule(
        client_sdr_id=client_sdr.id,
        start_date=start_date,
        end_date=end_date,
        linkedin_volume=linkedin_volume,
        linkedin_special_notes=linkedin_special_notes,
        email_volume=email_volume,
        email_special_notes=email_special_notes,
        week=week,
    )
    db.session.add(schedule)
    db.session.commit()

    return schedule


def basic_sdr_email_bank(
    client_sdr: ClientSDR,
    active: Optional[bool] = True,
    email_address: Optional[str] = "test_email_address",
    email_type: Optional[EmailType] = EmailType.ANCHOR,
    nylas_auth_code: Optional[str] = "test_nylas_auth_code",
    nylas_account_id: Optional[str] = "test_nylas_account_id",
    nylas_active: Optional[bool] = True,
) -> SDREmailBank:
    email_bank: SDREmailBank = SDREmailBank(
        client_sdr_id=client_sdr.id,
        active=active,
        email_address=email_address,
        email_type=email_type,
        nylas_auth_code=nylas_auth_code,
        nylas_account_id=nylas_account_id,
        nylas_active=nylas_active,
    )
    db.session.add(email_bank)
    db.session.commit()

    return email_bank


def basic_sdr_email_send_schedule(
    client_sdr: ClientSDR,
    email_bank: SDREmailBank,
    time_zone: Optional[str] = "America/Los_Angeles",
    days: Optional[list[int]] = [0, 1, 2, 3, 4],
    start_time: Optional[time] = time(hour=9, minute=0, second=0),
    end_time: Optional[time] = time(hour=17, minute=0, second=0),
) -> SDREmailSendSchedule:
    email_send_schedule: SDREmailSendSchedule = SDREmailSendSchedule(
        client_sdr_id=client_sdr.id,
        email_bank_id=email_bank.id,
        time_zone=time_zone,
        days=days,
        start_time=start_time,
        end_time=end_time,
    )
    db.session.add(email_send_schedule)
    db.session.commit()

    return email_send_schedule


def clear_all_entities(SQLAlchemyObject):
    echos = SQLAlchemyObject.query.all()
    for e in echos:
        db.session.delete(e)
    db.session.commit()


def test_simple_test():
    assert True


def test_simple_test_2():
    assert True


def test_socket_blocks():
    import requests

    with pytest.raises(Exception):
        response = requests.request("GET", "http://google.com")
