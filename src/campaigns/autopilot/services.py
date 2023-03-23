from app import db, celery
from model_import import (
    Prospect,
    Client,
    ClientSDR,
    ClientArchetype,
    GeneratedMessageType,
    GeneratedMessageCTA,
    OutboundCampaign
)
from src.utils.slack import send_slack_message, URL_MAP
from src.utils.datetime.dateutils import get_next_next_monday_sunday
from src.campaigns.services import (
    create_outbound_campaign,
    generate_campaign,
)
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import func

SLACK_CHANNEL = URL_MAP["operations-campaign-generation"]


def collect_and_generate_all_autopilot_campaigns():

    # Get all active clients
    active_clients = Client.query.filter_by(active=True).all()

    # Get all SDRs for each client that has autopilot_enabled
    sdrs: list[ClientSDR] = []
    for client in active_clients:
        client_sdrs = ClientSDR.query.filter(
            ClientSDR.client_id == client.id,
            ClientSDR.autopilot_enabled == True
        ).all()
        sdrs.extend(client_sdrs)

    # Generate campaigns for SDRs, using another function
    for sdr in sdrs:
        collect_and_generate_autopilot_campaign_for_sdr(sdr.id)


@celery.task(bind=True, max_retries=1)
def collect_and_generate_autopilot_campaign_for_sdr(self, client_sdr_id: int) -> tuple[bool, str]:
    try:
        # Get SDR
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        # Get active archetypes for SDR. If more than one, block and send slack message
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == client_sdr.id,
            ClientArchetype.active == True
        ).all()
        if len(archetypes) > 1:
            send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Too many active archetypes.", [SLACK_CHANNEL], blocks="")
            return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Too many active archetypes"

        # Get date of next next monday, and next next sunday (campaign timespan)
        next_next_monday, next_next_sunday = get_next_next_monday_sunday(
            datetime.today())

        # Generated types stores the campaign types which were generated
        generated_types = []

        # Generate campaign for LinkedIn given SLAs for the SDR
        if client_sdr.weekly_li_outbound_target is not None and client_sdr.weekly_li_outbound_target > 0:       # LinkedIn
            # Get CTAs for archetype. If none, block and send slack message
            ctas: list[GeneratedMessageCTA] = GeneratedMessageCTA.query.filter(
                GeneratedMessageCTA.archetype_id == archetypes[0].id,
                GeneratedMessageCTA.active == True
            ).all()
            if len(ctas) == 0:
                send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). No active CTAs for LinkedIn.", [SLACK_CHANNEL], blocks="")
                return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): No active CTAs for LinkedIn"

            # Check that SLA has not been filled and generate campaign if not
            sla_count = get_sla_count(
                client_sdr_id, archetypes[0].id, GeneratedMessageType.LINKEDIN, datetime.today())
            if sla_count < client_sdr.weekly_li_outbound_target:
                num_can_generate = client_sdr.weekly_li_outbound_target - sla_count
                # Create the campaign
                oc = create_outbound_campaign(
                    prospect_ids=[],
                    num_prospects=num_can_generate,
                    campaign_type=GeneratedMessageType.LINKEDIN,
                    client_archetype_id=archetypes[0].id,
                    client_sdr_id=client_sdr.id,
                    campaign_start_date=next_next_monday,
                    campaign_end_date=next_next_sunday,
                    ctas=[cta.id for cta in ctas],
                )
                if not oc:
                    send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error creating LINKEDIN campaign.", [SLACK_CHANNEL], blocks="")
                    return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Error creating LINKEDIN campaign"
                # Generate the campaign
                generating = generate_campaign(oc.id)
                if not generating:
                    send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error queuing LINKEDIN messages for generation.", [SLACK_CHANNEL], blocks="")
                    return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Error queuing LINKEDIN messages for generation"
                generated_types.append(GeneratedMessageType.LINKEDIN.value)
            else:
                send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). SLA for LinkedIn has been filled.", [SLACK_CHANNEL], blocks="")
                return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): SLA for LinkedIn has been filled"

        # Generate campaign for Email given SLAs for the SDR
        if client_sdr.weekly_email_outbound_target is not None and client_sdr.weekly_email_outbound_target > 0:   # Email
            # Check that SLA has not been filled:
            sla_count = get_sla_count(
                client_sdr_id, archetypes[0].id, GeneratedMessageType.EMAIL, datetime.today())
            if sla_count < client_sdr.weekly_email_outbound_target:
                num_can_generate = client_sdr.weekly_email_outbound_target - sla_count
                # Create the campaign
                oc = create_outbound_campaign(
                    prospect_ids=[],
                    num_prospects=num_can_generate,
                    campaign_type=GeneratedMessageType.EMAIL,
                    client_archetype_id=archetypes[0].id,
                    client_sdr_id=client_sdr.id,
                    campaign_start_date=next_next_monday,
                    campaign_end_date=next_next_sunday,
                    ctas=[cta.id for cta in ctas],
                )
                if not oc:
                    send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error creating EMAIL campaign.", [SLACK_CHANNEL], blocks="")
                    return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Error creating EMAIL campaign"
                # Generate the campaign
                generating = generate_campaign(oc.id)
                if not generating:
                    send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error queuing EMAIL messages for generation.", [SLACK_CHANNEL], blocks="")
                    return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Error queuing EMAIL messages for generation"
                generated_types.append(GeneratedMessageType.EMAIL.value)
            else:
                send_slack_message(f"🤖 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). SLA for Email has been filled.", [SLACK_CHANNEL], blocks="")
                return False, f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): SLA for Email has been filled"

        db.session.commit()
        send_slack_message(f"🤖 Autopilot Campaign successfully queued for {generated_types} generation: {client_sdr.name} (#{client_sdr.id})", [SLACK_CHANNEL], blocks="")
        return True, f"Autopilot Campaign successfully queued for {generated_types} generation: {client_sdr.name} (#{client_sdr.id})"
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def get_sla_count(client_sdr_id: int, client_archetype_id: int, campaign_type: GeneratedMessageType, autopilot_trigger_date: Optional[datetime]) -> int:
    """Gets the SLA count.

    We get the SLA count by counting the number of Prospects in campaigns that are marked as starting
    in two mondays away from the current day. The two week delay is to account for the time it takes to
    review messages and queue campaigns to be sent.

    For example:
    If today is Monday (1/1), we first get the next Monday (1/8) and then the Monday after that (1/15).
    We then count the number of Prospects in campaigns that are marked as starting on 1/15.

    Args:
        client_sdr_id (int): The ID of the SDR
        client_archetype_id (int): The ID of the archetype
        campaign_type (GeneratedMessageType): The type of campaign
        autopilot_trigger_date (Optional[datetime.date], optional): The start date. Defaults to datetime.date.today().

    Returns:
        int: The number of prospects in campaigns that are marked as starting on the next next monday
    """
    autopilot_trigger_date = autopilot_trigger_date or datetime.today()

    # Calculate next next monday
    next_next_monday, sunday = get_next_next_monday_sunday(
        autopilot_trigger_date)

    # Get campaigns that are marked as starting on next next monday
    campaigns: list[OutboundCampaign] = OutboundCampaign.query.filter(
        OutboundCampaign.client_sdr_id == client_sdr_id,
        OutboundCampaign.campaign_type == campaign_type,
        OutboundCampaign.client_archetype_id == client_archetype_id,
        func.date(OutboundCampaign.campaign_start_date) == next_next_monday.date()
    ).all()

    # Count the number of prospects in each campaign
    num_prospects = 0
    for campaign in campaigns:
        num_prospects += len(campaign.prospect_ids)

    return num_prospects
