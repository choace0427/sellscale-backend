from app import db, app
from test_utils import test_app
from decorators import use_app_context
import datetime

from test_utils import (
    basic_client,
    basic_archetype,
    basic_client_sdr,
    basic_outbound_campaign,
    basic_prospect,
    basic_prospect_email,
)
from src.campaigns.services import (
    get_outbound_campaign_details,
    get_outbound_campaigns,
    get_outbound_campaign_analytics,
    get_email_campaign_analytics,
    create_outbound_campaign,
    smart_get_prospects_for_campaign,
)
from model_import import (
    GeneratedMessageType,
    ProspectEmailStatus,
    ProspectEmailOutreachStatus,
)
import mock


@use_app_context
def test_get_outbound_campaign_details():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr
    )

    response = get_outbound_campaign_details(client_sdr.id, campaign.id)
    assert response.get("status_code") == 200
    assert response.get("campaign_details").get("campaign_raw").get("id") == campaign.id
    assert response.get("campaign_details").get("prospects")[0].get("id") == prospect.id


@use_app_context
def test_get_outbound_campaigns():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr, name="Aa"
    )
    campaign_2 = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr, name="Ab"
    )
    campaign_3 = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr, name="B"
    )

    search_for_name_response = get_outbound_campaigns(client_sdr.id, "A")
    assert search_for_name_response.get("total_count") == 2

    search_for_name_sorted_response = get_outbound_campaigns(
        client_sdr.id, "A", filters=[{"field": "name", "direction": 1}]
    )
    assert search_for_name_sorted_response.get("total_count") == 2
    assert search_for_name_sorted_response.get("outbound_campaigns")[0].name == "Aa"
    assert search_for_name_sorted_response.get("outbound_campaigns")[1].name == "Ab"

    sort_by_type_response = get_outbound_campaigns(
        client_sdr.id, campaign_type=["LINKEDIN"]
    )
    assert sort_by_type_response.get("total_count") == 1
    assert sort_by_type_response.get("outbound_campaigns")[0].name == "B"

    sort_by_status_response = get_outbound_campaigns(client_sdr.id, status=["PENDING"])
    assert sort_by_status_response.get("total_count") == 0

    all_response = get_outbound_campaigns(client_sdr.id)
    assert all_response.get("total_count") == 3

    limited_response = get_outbound_campaigns(client_sdr.id, limit=1)
    assert limited_response.get("total_count") == 3
    assert len(limited_response.get("outbound_campaigns")) == 1

    campaign_4 = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr, name="C"
    )
    campaign_4.campaign_start_date = datetime.datetime(2022, 1, 10).strftime("%Y-%m-%d")
    campaign_4.campaign_end_date = datetime.datetime(2022, 1, 17).strftime("%Y-%m-%d")
    db.session.add(campaign_4)
    db.session.commit()
    filter_by_date_response = get_outbound_campaigns(
        client_sdr.id, campaign_start_date="2022-01-01", campaign_end_date="2022-01-20"
    )
    assert filter_by_date_response.get("total_count") == 1
    assert filter_by_date_response.get("outbound_campaigns")[0].name == "C"


@use_app_context
@mock.patch(
    "src.campaigns.services.get_email_campaign_analytics", return_value={"test": "test"}
)
@mock.patch(
    "src.campaigns.services.get_linkedin_campaign_analytics",
    return_value={"test": "test"},
)
def test_get_outbound_campaign_analytics(li_mock, email_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign_email = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr
    )
    campaign_linkedin = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr
    )

    response = get_outbound_campaign_analytics(campaign_email.id)
    assert response == {"test": "test"}
    assert email_mock.called_once
    assert not li_mock.called

    response = get_outbound_campaign_analytics(campaign_linkedin.id)
    assert response == {"test": "test"}
    assert li_mock.called_once
    assert email_mock.called_once


@use_app_context
def test_get_email_campaign_analytics():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect_0 = basic_prospect(client, archetype, client_sdr)
    prospect_1 = basic_prospect(client, archetype, client_sdr)
    email_0 = basic_prospect_email(
        prospect_0,
        ProspectEmailStatus.SENT,
        ProspectEmailOutreachStatus.SENT_OUTREACH,
    )
    email_1 = basic_prospect_email(
        prospect_1,
        ProspectEmailStatus.SENT,
        ProspectEmailOutreachStatus.SCHEDULING,
    )
    campaign = basic_outbound_campaign(
        [prospect_0.id, prospect_1.id],
        GeneratedMessageType.EMAIL,
        archetype,
        client_sdr,
    )

    response = get_email_campaign_analytics(campaign.id)
    assert response == {
        "campaign_id": campaign.id,
        "campaign_type": campaign.campaign_type.value,
        "campaign_name": campaign.name,
        "campaign_start_date": campaign.campaign_start_date,
        "campaign_end_date": campaign.campaign_end_date,
        "all_prospects": [prospect_0.id, prospect_1.id],
        "not_sent": [],
        "email_bounced": [],
        "email_sent": [prospect_0.id],
        "email_opened": [],
        "email_accepted": [],
        "email_replied": [],
        "prospect_scheduling": [prospect_1.id],
        "prospect_not_interested": [],
        "prospect_demo_set": [],
        "prospect_demo_won": [],
        "prospect_demo_lost": [],
    }


@use_app_context
def test_create_outbound_campaign():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    archetype = basic_archetype(client, client_sdr)
    archetype_id = archetype.id
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id
    prospect_2 = basic_prospect(client, archetype, client_sdr)
    prospect_2_id = prospect_2.id
    prospect_3 = basic_prospect(client, archetype, client_sdr)
    prospect_3_id = prospect_3.id
    prospect.health_check_score = 0
    prospect_2.health_check_score = 100
    prospect_3.health_check_score = 50
    db.session.add_all([prospect, prospect_2, prospect_3])
    db.session.commit()

    start_date = datetime.datetime(2023, 1, 1)
    end_date = datetime.datetime(2023, 1, 8)

    campaign = create_outbound_campaign(
        prospect_ids=[prospect.id],
        num_prospects=2,
        campaign_type=GeneratedMessageType.LINKEDIN.value,
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date=start_date,
        campaign_end_date=end_date,
        ctas=[archetype_id],
    )
    assert campaign.name == "Testing archetype #1"
    assert campaign.canonical_name == "Testing archetype, 2, {}".format(str(start_date))
    assert prospect_id in campaign.prospect_ids
    assert prospect_2_id in campaign.prospect_ids
    assert prospect_3_id not in campaign.prospect_ids


@use_app_context
def test_smart_get_prospects_for_campaign():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    archetype_id = archetype.id
    high_prospect = basic_prospect(client, archetype, client_sdr)
    medium_prospect = basic_prospect(client, archetype, client_sdr)
    low_prospect = basic_prospect(client, archetype, client_sdr)
    high_prospect_id = high_prospect.id
    medium_prospect_id = medium_prospect.id
    low_prospect_id = low_prospect.id
    high_prospect.health_check_score = 100
    medium_prospect.health_check_score = 50
    low_prospect.health_check_score = 0
    db.session.add_all([high_prospect, medium_prospect, low_prospect])
    db.session.commit()

    all_prospects = smart_get_prospects_for_campaign(archetype_id, 3, "LINKEDIN")
    assert len(all_prospects) == 3

    higher_prospects = smart_get_prospects_for_campaign(archetype_id, 2, "LINKEDIN")
    assert len(higher_prospects) == 2
    assert high_prospect_id in higher_prospects
    assert medium_prospect_id in higher_prospects
    assert low_prospect_id not in higher_prospects

    prospect_no_score = basic_prospect(client, archetype, client_sdr)
    prospect_no_score_id = prospect_no_score.id
    all_prospects = smart_get_prospects_for_campaign(archetype_id, 4, "LINKEDIN")
    assert len(all_prospects) == 4
    assert prospect_no_score_id in all_prospects

    prospect_high_intent = basic_prospect(client, archetype, client_sdr)
    prospect_high_intent_id = prospect_high_intent.id
    prospect_high_intent.li_intent_score = 100
    db.session.add(prospect_high_intent)
    db.session.commit()
    all_prospects = smart_get_prospects_for_campaign(archetype_id, 4, "LINKEDIN")
    assert len(all_prospects) == 4
    assert prospect_high_intent_id in all_prospects
    assert prospect_no_score_id not in all_prospects

