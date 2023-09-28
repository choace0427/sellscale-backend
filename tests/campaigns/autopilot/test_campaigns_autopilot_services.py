from app import db
from test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_client_sdr,
    basic_prospect,
    basic_prospect_email,
    basic_sla_schedule,
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
    ClientSDR,
)
from src.campaigns.autopilot.services import (
    collect_and_generate_autopilot_campaign_for_sdr,
    get_sla_count,
)
import mock


@use_app_context
@mock.patch("src.campaigns.autopilot.services.generate_campaign")
@mock.patch("src.campaigns.autopilot.services.send_slack_message")
def test_collect_and_generate_autopilot_campaign_for_sdr(
    send_slack_mock, gen_campaign_mock
):
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
    schedule = basic_sla_schedule(
        client_sdr, oc.campaign_start_date + timedelta(days=7), 1, '', 1
    )
    schedule_2 = basic_sla_schedule(
        client_sdr, oc.campaign_start_date, 1, '', 1
    )
    campaign_start_date = oc.campaign_start_date
    archetype.active = True
    archetype_id = archetype.id
    archetype_2.active = True

    # Constraint: Must have only 1 archetype
    status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr.id)
    assert status == (
        False,
        f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Too many active archetypes",
    )

    # Constraint: Must have at least 1 CTA for LinkedIn
    archetype_2.active = False
    db.session.add(archetype_2)
    db.session.commit()
    status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr.id)
    assert status == (
        False,
        f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): No active CTAs for LinkedIn",
    )

    # Constraint: Must have SLA space for LinkedIn
    cta = basic_generated_message_cta(ClientArchetype.query.get(archetype_id))
    with freeze_time(campaign_start_date - timedelta(days=14)):
        status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr.id)
        campaigns = OutboundCampaign.query.filter_by(client_sdr_id=client_sdr_id).all()
        assert len(campaigns) == 2

        # Constraint: Must have SLA space for Email
        schedule_2.email_volume = 1
        schedule_2.linkedin_volume = 2
        db.session.commit()
        status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr_id)
        assert status == (
            True,
            f"Autopilot Campaign successfully queued for ['LINKEDIN'] generation: Test SDR (#{client_sdr.id})",
        )
        campaigns = OutboundCampaign.query.filter_by(client_sdr_id=client_sdr_id).all()
        assert len(campaigns) == 3
        for campaign in campaigns:
            assert campaign.campaign_start_date.weekday() == 0  # Monday
            assert campaign.campaign_end_date.weekday() == 6  # Sunday
            assert campaign.campaign_start_date.date() == campaign_start_date.date()

        # Works. Should generate a campaign for email. The previous test should have generated a campaign for LinkedIn
        schedule_2.email_volume = 2
        db.session.commit()
        status = collect_and_generate_autopilot_campaign_for_sdr(client_sdr_id)
        assert status == (
            True,
            f"Autopilot Campaign successfully queued for ['EMAIL'] generation: {client_sdr.name} (#{client_sdr.id})",
        )
        campaigns = OutboundCampaign.query.filter_by(client_sdr_id=client_sdr_id).all()
        assert len(campaigns) == 4
        for campaign in campaigns:
            assert campaign.campaign_start_date.weekday() == 0  # Monday
            assert campaign.campaign_end_date.weekday() == 6  # Sunday
            assert campaign.campaign_start_date.date() == campaign_start_date.date()

    # Give a custom date to generate the campaign
    status = collect_and_generate_autopilot_campaign_for_sdr(
        client_sdr.id, schedule.start_date
    )
    assert status == (
        True,
        f"Autopilot Campaign successfully queued for ['LINKEDIN', 'EMAIL'] generation: {client_sdr.name} (#{client_sdr.id})",
    )
    campaigns = OutboundCampaign.query.filter_by(client_sdr_id=client_sdr_id).order_by(OutboundCampaign.created_at.desc()).all()
    assert len(campaigns) == 6
    assert campaigns[0].campaign_start_date == schedule.start_date
    assert campaigns[1].campaign_start_date == schedule.start_date
    assert campaigns[2].campaign_start_date.date() == schedule_2.start_date.date()
    assert campaigns[3].campaign_start_date.date() == schedule_2.start_date.date()
    assert campaigns[4].campaign_start_date.date() == schedule_2.start_date.date()
    assert campaigns[5].campaign_start_date.date() == schedule_2.start_date.date()


@use_app_context
def test_get_sla_count():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    oc = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr
    )

    # Get SLA of the campaign's week
    sla_count = get_sla_count(
        client_sdr.id, archetype.id, GeneratedMessageType.EMAIL, oc.campaign_start_date.date()
    )
    assert sla_count == 1

    # Next monday is 1 week before the campaign start date, which is set to next monday.
    this_monday = oc.campaign_start_date - timedelta(days=7)
    sla_count = get_sla_count(
        client_sdr.id, archetype.id, GeneratedMessageType.EMAIL, this_monday.date()
    )
    assert sla_count == 0
