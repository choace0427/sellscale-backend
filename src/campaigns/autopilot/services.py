from app import db, celery
from model_import import (
    Prospect,
    Client,
    ClientSDR,
    ClientArchetype,
    GeneratedMessageType,
    OutboundCampaign
)
from src.utils.slack import send_slack_message
from typing import Optional

from datetime import datetime, timedelta
from sqlalchemy import func


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


# @celery.task(bind=True, max_retries=1)
def collect_and_generate_autopilot_campaign_for_sdr(self, client_sdr_id: int) -> tuple[bool, str]:
    # Get SDR
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get active archetypes for SDR
    archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr.id,
        ClientArchetype.active == True
    ).all()

    # If more than one active archetype, block and send slack message
    if len(archetypes) > 1:
        # TODO: SEND SLACK MESSAGE INTO A CHANNEL
        # send_slack_message()
        return False, f"Autopilot Campaign not created for {client_sdr.name}: Too many active archetypes"

    # Generate campaign for LinkedIn given SLAs for the SDR
    if client_sdr.weekly_li_outbound_target is not None and client_sdr.weekly_li_outbound_target > 0:       # LinkedIn
        # Check that SLA has not been filled:
        sla_count = get_sla_count(client_sdr_id, archetypes[0].id, GeneratedMessageType.LINKEDIN)

        if sla_count < client_sdr.weekly_li_outbound_target:
            num_can_generate = client_sdr.weekly_li_outbound_target - sla_count
            # TODO: GENERATE
        else:
            # TODO: SEND SLACK MESSAGE INTO A CHANNEL
            return False, f"Autopilot Campaign not created for {client_sdr.name}: SLA for LinkedIn has been filled"

    # Generate campaign for Email given SLAs for the SDR
    if client_sdr.weekly_email_outbound_target is not None and client_sdr.weekly_email_outbound_target > 0:   # Email
        # Check that SLA has not been filled:
        sla_count = get_sla_count(client_sdr_id, archetypes[0].id, GeneratedMessageType.EMAIL)
        if sla_count < client_sdr.weekly_email_outbound_target:
            num_can_generate = client_sdr.weekly_email_outbound_target - sla_count
            # TODO: GENERATE
        else:
            # TODO: SEND SLACK MESSAGE INTO A CHANNEL
            return False, f"Autopilot Campaign not created for {client_sdr.name}: SLA for Email has been filled"


def get_sla_count(client_sdr_id: int, client_archetype_id: int, campaign_type: GeneratedMessageType, autopilot_trigger_date: Optional[datetime] = datetime.today()) -> int:
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
    # Calculate next next monday
    days_until_next_monday = (7 - autopilot_trigger_date.weekday()) % 7
    if days_until_next_monday == 0: # If today is Monday
        days_until_next_monday = 7
    next_monday = autopilot_trigger_date + timedelta(days=days_until_next_monday)
    next_next_monday = next_monday + timedelta(days=7)

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
