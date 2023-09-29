from app import db, celery
from model_import import (
    Prospect,
    Client,
    ClientSDR,
    ClientArchetype,
    GeneratedMessageType,
    GeneratedMessageCTA,
    OutboundCampaign,
    OutboundCampaignStatus,
)
from src.client.models import SLASchedule
from src.utils.datetime.dateparse_utils import convert_string_to_datetime
from src.utils.slack import send_slack_message, URL_MAP
from src.utils.datetime.dateutils import get_current_monday_sunday, get_next_next_monday_sunday
from src.campaigns.services import (
    create_outbound_campaign,
    generate_campaign,
    smart_get_prospects_for_campaign,
)
from typing import Optional
from datetime import date, datetime, timedelta
from sqlalchemy import func
from sqlalchemy import and_, or_, not_

SLACK_CHANNEL = URL_MAP["operations-campaign-generation"]


def collect_and_generate_all_autopilot_campaigns(
    start_date: Optional[datetime] = None,
):
    if type(start_date) == str:
        start_date = convert_string_to_datetime(start_date)

    # Get all active clients
    active_clients = Client.query.filter_by(
        active=True,
        id=3,
    ).all()

    # Get all SDRs for each client that has autopilot_enabled
    sdrs: list[ClientSDR] = []
    for client in active_clients:
        client_sdrs: list[ClientSDR] = ClientSDR.query.filter(
            ClientSDR.client_id == client.id, ClientSDR.autopilot_enabled == True
        ).all()
        sdrs.extend(client_sdrs)

    # Generate campaigns for SDRs, using another function
    for i, sdr in enumerate(sdrs):
        sdr_id = sdr.id

        collect_and_generate_autopilot_campaign_for_sdr.apply_async(
            args=[sdr_id, start_date],
            queue="message_generation",
            routing_key="message_generation",
        )


@celery.task(bind=True, max_retries=1)
def collect_and_generate_autopilot_campaign_for_sdr(
    self, client_sdr_id: int, custom_start_date: Optional[datetime] = None
) -> tuple[bool, str]:
    try:
        # Get SDR
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        # Get active archetypes for SDR. If more than one, block and send slack message
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == client_sdr.id,
            ClientArchetype.active == True,
        ).all()
        if len(archetypes) > 1:
            send_slack_message(
                f"🤖 ❌ 👥 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Too many active archetypes.",
                [SLACK_CHANNEL],
            )
            return (
                False,
                f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Too many active archetypes",
            )
        elif len(archetypes) == 0:
            send_slack_message(
                f"🤖 ❌ 👤 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). No active archetypes.",
                [SLACK_CHANNEL],
            )
            return (
                False,
                f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): No active archetypes",
            )

        # Default to Getting date of next next monday, and next next sunday (campaign timespan)
        start_date, end_date = get_next_next_monday_sunday(
            datetime.today()
        )

        # If custom_start_date is provided, then use the monday and sunday of that week
        if custom_start_date:
            if type(custom_start_date) == str:
                custom_start_date = convert_string_to_datetime(custom_start_date)
            start_date, end_date = get_current_monday_sunday(custom_start_date)

        # Get the SLA Schedule entry for this date range
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr.id,
            func.date(SLASchedule.start_date) == start_date,
        ).first()
        if not sla_schedule:
            send_slack_message(
                f"🤖 ❌ 📅 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). No SLA Schedule entry for {start_date}.",
                [SLACK_CHANNEL],
            )
            return (
                False,
                f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): No SLA Schedule entry for {start_date}",
            )

        # Generated types stores the campaign types which were generated
        generated_types = []

        # Generate campaign for LinkedIn given SLAs for the SDR
        if (
            sla_schedule.linkedin_volume > 0
        ):  # LinkedIn

            # Don't use CTAs that will expire in the next 10 days
            current_date = datetime.utcnow()
            in_10_days = current_date + timedelta(days=10)

            # Get CTAs for archetype. If none, block and send slack message
            ctas: list[GeneratedMessageCTA] = GeneratedMessageCTA.query.filter(
                GeneratedMessageCTA.archetype_id == archetypes[0].id,
                GeneratedMessageCTA.active == True,
                or_(
                    GeneratedMessageCTA.expiration_date == None,
                    GeneratedMessageCTA.expiration_date > in_10_days,
                ),
            ).all()
            if len(ctas) == 0:
                send_slack_message(
                    f"🤖 ❌ 🖊️ Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). No active CTAs for LinkedIn.",
                    [SLACK_CHANNEL],
                )
                return (
                    False,
                    f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): No active CTAs for LinkedIn",
                )

            # Check that SLA has not been filled and generate campaign if not
            sla_count = get_sla_count(
                client_sdr_id,
                archetypes[0].id,
                GeneratedMessageType.LINKEDIN,
                start_date=start_date,
            )
            if sla_count < sla_schedule.linkedin_volume:
                num_can_generate = sla_schedule.linkedin_volume - sla_count
                # Check that there are enough prospects to generate the campaign
                num_available_prospects = len(
                    smart_get_prospects_for_campaign(
                        archetypes[0].id,
                        num_can_generate,
                        GeneratedMessageType.LINKEDIN,
                    )
                )
                if num_can_generate <= num_available_prospects:
                    # Create the campaign
                    oc = create_outbound_campaign(
                        prospect_ids=[],
                        num_prospects=num_can_generate,
                        campaign_type=GeneratedMessageType.LINKEDIN,
                        client_archetype_id=archetypes[0].id,
                        client_sdr_id=client_sdr.id,
                        campaign_start_date=start_date,
                        campaign_end_date=end_date,
                        ctas=[cta.id for cta in ctas],
                    )
                    if not oc:
                        send_slack_message(
                            f"🤖 ❌ ❓ Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error creating LINKEDIN campaign.",
                            [SLACK_CHANNEL],
                        )
                    # Generate the campaign
                    else:
                        generating = generate_campaign(oc.id)
                        if not generating:
                            send_slack_message(
                                f"🤖 ❌ ❓ Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error queuing LINKEDIN messages for generation.",
                                [SLACK_CHANNEL],
                            )
                        else:
                            generated_types.append(GeneratedMessageType.LINKEDIN.value)
                else:
                    send_slack_message(
                        f"🤖 ❌ 🧑‍🤝‍🧑 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Not enough prospects to generate LINKEDIN campaign.",
                        [SLACK_CHANNEL],
                    )
            else:
                send_slack_message(
                    f"🤖 ✅ Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). SLA for LinkedIn has been filled.",
                    [SLACK_CHANNEL],
                )

        # Generate campaign for Email given SLAs for the SDR
        if (
            sla_schedule.email_volume > 0
        ):  # Email
            # Check that SLA has not been filled:
            sla_count = get_sla_count(
                client_sdr_id,
                archetypes[0].id,
                GeneratedMessageType.EMAIL,
                start_date=start_date,
            )
            print(sla_count, sla_schedule.email_volume)
            if sla_count < sla_schedule.email_volume:
                num_can_generate = sla_schedule.email_volume - sla_count
                # Check that there are enough prospects to generate the campaign
                num_available_prospects = len(
                    smart_get_prospects_for_campaign(
                        archetypes[0].id, num_can_generate, GeneratedMessageType.EMAIL
                    )
                )
                if num_can_generate <= num_available_prospects:
                    # Create the campaign
                    oc = create_outbound_campaign(
                        prospect_ids=[],
                        num_prospects=num_can_generate,
                        campaign_type=GeneratedMessageType.EMAIL,
                        client_archetype_id=archetypes[0].id,
                        client_sdr_id=client_sdr.id,
                        campaign_start_date=start_date,
                        campaign_end_date=end_date,
                        ctas=[cta.id for cta in ctas],
                    )
                    if not oc:
                        send_slack_message(
                            f"🤖 ❌ ❓ Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error creating EMAIL campaign.",
                            [SLACK_CHANNEL],
                        )
                    # Generate the campaign
                    else:
                        generating = generate_campaign(oc.id)
                        if not generating:
                            send_slack_message(
                                f"🤖 ❌ ❓ Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Error queuing EMAIL messages for generation.",
                                [SLACK_CHANNEL],
                            )
                        else:
                            generated_types.append(GeneratedMessageType.EMAIL.value)
                else:
                    send_slack_message(
                        f"🤖 ❌ 🧑‍🤝‍🧑 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). Not enough prospects to generate EMAIL campaign.",
                        [SLACK_CHANNEL],
                    )
            else:
                send_slack_message(
                    f"🤖 ✅ Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). SLA for Email has been filled.",
                    [SLACK_CHANNEL],
                )

        if len(generated_types) == 0:
            return (
                False,
                f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Neither Email nor LinkedIn generated.",
            )

        send_slack_message(
            f"🤖 ✅ Autopilot Campaign successfully queued for {generated_types} generation: {client_sdr.name} (#{client_sdr.id})",
            [SLACK_CHANNEL],
        )

        return (
            True,
            f"Autopilot Campaign successfully queued for {generated_types} generation: {client_sdr.name} (#{client_sdr.id})",
        )
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def get_sla_count(
    client_sdr_id: int,
    client_archetype_id: int,
    campaign_type: GeneratedMessageType,
    start_date: Optional[date],
) -> int:
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
        start_date (Optional[datetime.date], optional): The start date. Defaults to datetime.date.today().

    Returns:
        int: The number of prospects in campaigns that are marked as starting on the next next monday
    """
    start_date = start_date or datetime.today()

    # Get campaigns that are marked as starting on the provided date
    campaigns: list[OutboundCampaign] = OutboundCampaign.query.filter(
        OutboundCampaign.client_sdr_id == client_sdr_id,
        OutboundCampaign.campaign_type == campaign_type,
        OutboundCampaign.client_archetype_id == client_archetype_id,
        OutboundCampaign.status != OutboundCampaignStatus.CANCELLED,
        func.date(OutboundCampaign.campaign_start_date) == start_date,
    ).all()

    # Count the number of prospects in each campaign
    num_prospects = 0
    for campaign in campaigns:
        num_prospects += len(campaign.prospect_ids)

    return num_prospects
