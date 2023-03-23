from app import db
from test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_client_sdr,
    basic_prospect,
    basic_prospect_email,
    basic_generated_message_cta,
    basic_outbound_campaign,
)
from decorators import use_app_context
from freezegun import freeze_time
from datetime import datetime, timedelta
from model_import import (
    GeneratedMessageType,
    OutboundCampaign,
    ClientArchetype,
    ClientSDR
)
from src.campaigns.autopilot.services import (
    collect_and_generate_autopilot_campaign_for_sdr,
    get_sla_count
)


@use_app_context
def test_collect_and_generate_autopilot_campaign_for_sdr():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    client_sdr.weekly_li_outbound_target = 1
    client_sdr.weekly_email_outbound_target = 1
    archetype = basic_archetype(client, client_sdr)
    archetype_2 = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    oc = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr
    )
    oc = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr
    )
    campaign_start_date = oc.campaign_start_date
    archetype.active = True
    archetype_id = archetype.id
    archetype_2.active = True

    # Constraint: Must have only 1 archetype
    status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr.id)
    assert status == (False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Too many active archetypes")

    # Constraint: Must have at least 1 CTA for LinkedIn
    archetype_2.active = False
    db.session.add(archetype_2)
    db.session.commit()
    client_sdr.weekly_li_outbound_target = 75
    status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr.id)
    assert status == (False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): No active CTAs for LinkedIn")

    # Constraint: Must have SLA space for LinkedIn
    cta = basic_generated_message_cta(ClientArchetype.query.get(archetype_id))
    with freeze_time(campaign_start_date - timedelta(days = 14)):
        status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr.id)
        assert status == (False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): SLA for LinkedIn has been filled")

        # Constraint: Must have SLA space for Email
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        sdr.weekly_li_outbound_target = 10
        status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr_id)
        assert status == (False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): SLA for Email has been filled")
        campaigns = OutboundCampaign.query.filter_by(client_sdr_id=client_sdr_id).all()
        assert len(campaigns) == 3
        for campaign in campaigns:
            assert campaign.campaign_start_date.weekday() == 0 # Monday
            assert campaign.campaign_end_date.weekday() == 6 # Sunday
            assert campaign.campaign_start_date.date() == campaign_start_date.date()

        # Works
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        sdr.weekly_email_outbound_target = 10
        sdr.weekly_li_outbound_target = 10
        status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr_id)
        assert status == (True, f"Autopilot Campaign successfully queued for ['LINKEDIN', 'EMAIL'] generation: {client_sdr.name} (#{client_sdr.id})")
        campaigns = OutboundCampaign.query.filter_by(client_sdr_id=client_sdr_id).all()
        assert len(campaigns) == 5
        for campaign in campaigns:
            assert campaign.campaign_start_date.weekday() == 0 # Monday
            assert campaign.campaign_end_date.weekday() == 6 # Sunday
            assert campaign.campaign_start_date.date() == campaign_start_date.date()


@use_app_context
def test_get_sla_count():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    oc = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr
    )

    # Last monday is 2 weeks before the campaign start date, which is set to next monday.
    last_monday = oc.campaign_start_date - timedelta(days=14)
    sla_count = get_sla_count(client_sdr.id, archetype.id, GeneratedMessageType.EMAIL, last_monday)
    assert sla_count == 1

    # Next monday is 1 week before the campaign start date, which is set to next monday.
    this_monday = oc.campaign_start_date - timedelta(days=7)
    sla_count = get_sla_count(client_sdr.id, archetype.id, GeneratedMessageType.EMAIL, this_monday)
    assert sla_count == 0
