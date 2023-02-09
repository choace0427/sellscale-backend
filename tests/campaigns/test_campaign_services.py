from app import db, app
from test_utils import test_app
import pytest
from decorators import use_app_context
import datetime
import json

from test_utils import (
    basic_client,
    basic_archetype,
    basic_client_sdr,
    basic_outbound_campaign,
    basic_email_schema,
    basic_prospect,
    basic_prospect_email,
)
from src.campaigns.services import get_outbound_campaign_analytics, get_email_campaign_analytics
from model_import import GeneratedMessageType, ProspectEmailStatus, ProspectEmailOutreachStatus
import mock


@use_app_context
@mock.patch("src.campaigns.services.get_email_campaign_analytics", return_value={"test": "test"})
@mock.patch("src.campaigns.services.get_linkedin_campaign_analytics", return_value={"test": "test"})
def test_get_outbound_campaign_analytics(li_mock, email_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign_email = basic_outbound_campaign([prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr)
    campaign_linkedin = basic_outbound_campaign([prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr)

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
    email_schema = basic_email_schema(archetype)
    email_0 = basic_prospect_email(prospect_0, email_schema, ProspectEmailStatus.SENT, ProspectEmailOutreachStatus.SENT_OUTREACH)
    email_1 = basic_prospect_email(prospect_1, email_schema, ProspectEmailStatus.SENT, ProspectEmailOutreachStatus.SCHEDULING)
    campaign = basic_outbound_campaign([prospect_0.id, prospect_1.id], GeneratedMessageType.EMAIL, archetype, client_sdr)


    response = get_email_campaign_analytics(campaign.id)
    assert response == {
        "campaign_id": campaign.id,
        "campaign_type": campaign.campaign_type.value,
        "campaign_name": campaign.name,
        "campaign_start_date": campaign.campaign_start_date,
        "campaign_end_date": campaign.campaign_end_date,
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