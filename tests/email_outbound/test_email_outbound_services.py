from src.email_outbound.models import (
    EmailCustomizedFieldTypes,
    SalesEngagementInteractionSource,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSS,
    EmailInteractionState,
    EmailSequenceState,
)
from src.email_outbound.services import (
    create_prospect_email,
    batch_mark_prospect_email_sent,
    update_prospect_email_flow_statuses,
    create_sales_engagement_interaction_raw,
    collect_and_update_status_from_ss_data,
    update_status_from_ss_data,
)
from tests.test_utils.test_utils import (
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_generated_message,
    basic_sei_raw,
    basic_sei_ss,
    basic_outbound_campaign,
    basic_prospect_email,
)
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import test_app
from app import db
from src.email_outbound.models import (
    EmailSchema,
    ProspectEmail,
    ProspectEmailStatus,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords,
)
from model_import import (
    GeneratedMessageType,
    GeneratedMessageStatus,
    OutboundCampaignStatus,
    ProspectStatus,
    Prospect,
    GeneratedMessage,
    OutboundCampaign,
)
import mock


@use_app_context
def test_create_prospect_email():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect = basic_prospect(client, archetype)
    outbound_campaign = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, sdr
    )
    personalized_first_line = basic_generated_message(prospect)

    prospect_email = create_prospect_email(
        prospect_id=prospect.id,
        personalized_first_line_id=personalized_first_line.id,
        outbound_campaign_id=outbound_campaign.id,
    )
    assert prospect_email.prospect_id == prospect.id
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT

    all_prospect_emails = ProspectEmail.query.all()
    assert len(all_prospect_emails) == 1
    assert all_prospect_emails[0].prospect_id == prospect.id
    assert all_prospect_emails[0].email_status == ProspectEmailStatus.DRAFT


@use_app_context
@mock.patch(
    "src.email_outbound.services.update_prospect_email_flow_statuses.apply_async",
    return_value=None,
)
def test_batch_mark_prospect_email_sent(update_mock):
    prospect_ids: list[int] = [1, 2, 3]
    assert update_mock.call_count == 0
    success = batch_mark_prospect_email_sent(prospect_ids, campaign_id=123)
    assert success
    assert update_mock.call_count == 3

    prospect_ids: list[int] = [1]
    success = batch_mark_prospect_email_sent(prospect_ids, campaign_id=123)
    assert success
    assert update_mock.call_count == 4
    assert update_mock.called_with(args=[1, 123])


@use_app_context
def test_update_prospect_email_flow_statuses():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect_email = basic_prospect_email(prospect, ProspectEmailStatus.APPROVED)
    prospect_email_id = prospect_email.id
    personalized_first_line = basic_generated_message(prospect)
    personalized_first_line_id = personalized_first_line.id
    outbound_campaign = basic_outbound_campaign(
        [prospect_id], GeneratedMessageType.EMAIL, archetype, sdr
    )
    outbound_campaign_id = outbound_campaign.id

    prospect.approved_prospect_email_id = prospect_email.id
    prospect_email.personalized_first_line = personalized_first_line.id
    outbound_campaign_id = outbound_campaign.id
    db.session.add(prospect)
    db.session.add(personalized_first_line)
    db.session.commit()

    assert prospect_email.email_status == ProspectEmailStatus.APPROVED
    assert prospect.status == ProspectStatus.PROSPECTED
    assert personalized_first_line.message_status == GeneratedMessageStatus.DRAFT
    assert outbound_campaign.status == OutboundCampaignStatus.READY_TO_SEND
    message, success = update_prospect_email_flow_statuses(
        prospect_id, outbound_campaign_id
    )
    assert success
    prospect_email = ProspectEmail.query.get(prospect_email_id)
    personalized_first_line = GeneratedMessage.query.get(personalized_first_line_id)
    outbound_campaign = OutboundCampaign.query.get(outbound_campaign_id)

    assert prospect_email.email_status == ProspectEmailStatus.SENT
    assert personalized_first_line.message_status == GeneratedMessageStatus.SENT
    assert outbound_campaign.status == OutboundCampaignStatus.COMPLETE


@use_app_context
def test_create_sales_engagement_interaction_raw():
    client = basic_client()
    archetype = basic_archetype(client)
    sdr = basic_client_sdr(client)

    client_id = client.id
    client_sdr_id = sdr.id
    payload = [{"Sequence Name": "test-sequence"}]
    source = SalesEngagementInteractionSource.OUTREACH.value
    sei_raw_id = create_sales_engagement_interaction_raw(
        client_id, client_sdr_id, payload, source
    )
    assert len(SalesEngagementInteractionRaw.query.all()) == 1
    sei_raw: SalesEngagementInteractionRaw = SalesEngagementInteractionRaw.query.get(
        sei_raw_id
    )
    assert sei_raw.client_id == client_id
    assert sei_raw.client_sdr_id == client_sdr_id
    assert sei_raw.csv_data == payload
    assert sei_raw.source.value == source
    assert sei_raw.sequence_name == "test-sequence"
    original_raw_id = sei_raw.id

    # No duplicates
    sei_raw_id = create_sales_engagement_interaction_raw(
        client_id, client_sdr_id, payload, source
    )
    assert len(SalesEngagementInteractionRaw.query.all()) == 1
    assert sei_raw_id == original_raw_id


@use_app_context
@mock.patch("src.email_outbound.services.update_status_from_ss_data.apply_async")
def test_collect_and_update_status_from_ss_data(update_status_from_ss_data_mock):
    client = basic_client()
    sdr = basic_client_sdr(client)
    sei_raw = basic_sei_raw(client, sdr)
    sei_ss = basic_sei_ss(client, sdr, sei_raw)
    sei_ss_id = sei_ss.id

    complete = collect_and_update_status_from_ss_data(sei_ss_id)
    assert complete == True
    assert update_status_from_ss_data_mock.called == True
    assert update_status_from_ss_data_mock.call_count == 1


@use_app_context
def test_update_status_from_ss_data():
    client = basic_client()
    archetype = basic_archetype(client)
    sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_email = basic_prospect_email(prospect, ProspectEmailStatus.SENT)
    sei_raw = basic_sei_raw(client, sdr)
    sei_ss = basic_sei_ss(client, sdr, sei_raw)
    client_id = client.id
    sdr_id = sdr.id
    prospect_id = prospect.id
    prospect_email_id = prospect_email.id
    sei_ss_id = sei_ss.id

    # Email sent
    prospect_dict = {
        "email": "test@email.com",
        "email_interaction_state": "EMAIL_SENT",
        "email_sequence_state": "COMPLETED",
    }
    updated = update_status_from_ss_data(client_id, sdr_id, prospect_dict, sei_ss_id)
    assert updated
    assert len(ProspectEmail.query.all()) == 1
    pe: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    assert pe.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    sr = ProspectEmailStatusRecords.query.all()
    assert len(sr) == 1
    assert sr[0].prospect_email_id == prospect_email_id
    assert sr[0].from_status == ProspectEmailOutreachStatus.UNKNOWN
    assert sr[0].to_status == ProspectEmailOutreachStatus.SENT_OUTREACH

    # Email opened
    opened_dict = {
        "email": "test@email.com",
        "email_interaction_state": "EMAIL_OPENED",
        "email_sequence_state": "COMPLETED",
    }
    updated = update_status_from_ss_data(client_id, sdr_id, opened_dict, sei_ss_id)
    assert updated
    assert len(ProspectEmail.query.all()) == 1
    pe: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    assert pe.outreach_status == ProspectEmailOutreachStatus.EMAIL_OPENED
    sr = ProspectEmailStatusRecords.query.all()
    assert len(sr) == 2
    assert sr[1].prospect_email_id == prospect_email_id
    assert sr[1].from_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    assert sr[1].to_status == ProspectEmailOutreachStatus.EMAIL_OPENED
