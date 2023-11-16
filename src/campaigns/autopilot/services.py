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

        if sdr.client_id == 46:
            continue

        collect_and_generate_autopilot_campaign_for_sdr.apply_async(
            args=[sdr_id, start_date],
            queue="message_generation",
            routing_key="message_generation",
        )


@celery.task(bind=True, max_retries=1)
def daily_collect_and_generate_campaigns_for_sdr(self):
    # If the current day is a weekend, then don't generate campaigns
    if datetime.today().weekday() in [5, 6]:
        return

    # Get active clients that have auto_generate_li_messages enabled
    clients: list[Client] = Client.query.filter(
        Client.active == True,
        Client.auto_generate_li_messages == True,
    ).all()
    client_ids = [client.id for client in clients]

    # Get all SDRs for each client that has auto_generate_li_messages
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.client_id.in_(client_ids),
        ClientSDR.active == True
    ).all()

    for sdr in sdrs:
        sdr_id = sdr.id
        collect_and_generate_autopilot_campaign_for_sdr.apply_async(
            args=[sdr_id, datetime.today(), True]
        )


@celery.task(bind=True, max_retries=1)
def collect_and_generate_autopilot_campaign_for_sdr(
    self,
    client_sdr_id: int,
    custom_start_date: Optional[datetime] = None,
    daily: bool = False,
) -> tuple[bool, str]:
    try:
        # Get SDR
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        # 1. Get the active LinkedIn archetypes
        linkedin_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == client_sdr.id,
            ClientArchetype.active == True,
            ClientArchetype.linkedin_active == True,
        ).all()
        if len(linkedin_archetypes) == 0:
            send_slack_message(
                f"🤖 ❌ 🧑‍🤝‍🧑 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). No active LinkedIn archetypes.",
                [SLACK_CHANNEL],
            )

        # 2. Get the active Email archetypes
        # TODO: Uncomment me when we autogenerate email cmapaigns
        # email_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        #     ClientArchetype.client_sdr_id == client_sdr.id,
        #     ClientArchetype.active == True,
        #     ClientArchetype.email_active == True,
        # ).all()
        # if len(email_archetypes) == 0:
        #     send_slack_message(
        #         f"🤖 ❌ 🧑‍🤝‍🧑 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). No active Email archetypes.",
        #         [SLACK_CHANNEL],
        #     )
        #     return (
        #         False,
        #         f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): No active Email archetypes",
        #     )

        # 3a. Default to Getting date of next next monday, and next next sunday (campaign timespan)
        start_date, end_date = get_next_next_monday_sunday(
            datetime.today()
        )

        # 3b. If custom_start_date is provided, then use the monday and sunday of that week
        if custom_start_date:
            if type(custom_start_date) == str:
                custom_start_date = convert_string_to_datetime(custom_start_date)
            start_date, end_date = get_current_monday_sunday(custom_start_date)

        # 3c. If daily is True, then use the current day and the next day
        if daily:
            start_date = datetime.today()
            end_date = start_date + timedelta(days=1)

        # 4a. Get the SLA Schedule entry for this date range
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr.id,
            func.date(SLASchedule.start_date) <= start_date,
            func.date(SLASchedule.end_date) >= end_date,
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

        # 4b. Campaigns generated will track which campaigns have been generated
        linkedin_campaigns_generated = []
        email_campaigns_generated = []

        # 5. Generate campaign for LinkedIn given SLAs for the SDR
        if (
            sla_schedule.linkedin_volume > 0
        ):
            # 5a. Get current date and date 10 days from now
            current_date = datetime.utcnow()
            in_10_days = current_date + timedelta(days=10)

            # 5a. Get the available SLA count for this SDR
            available_sla, total_sla, message = get_available_sla_count(
                client_sdr_id=client_sdr_id,
                campaign_type=GeneratedMessageType.LINKEDIN,
                start_date=start_date,
                per_day=True,
            )
            if available_sla == -1:
                send_slack_message(
                    f"🤖 ❌ 📅 Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}). {message}",
                    [SLACK_CHANNEL],
                )
                return (
                    False,
                    f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): {message}",
                )
            sla_per_campaign = available_sla // len(linkedin_archetypes)
            leftover_sla = available_sla % len(linkedin_archetypes)

            # 5b. Create a list of SLA counts for each archetype.
            # Example: 90 SLA, 3 archetypes -> [30, 30, 30]. 90 SLA, 4 archetypes -> [22, 22, 23, 23]
            sla_counts = [sla_per_campaign] * (len(linkedin_archetypes) - leftover_sla) + [sla_per_campaign + 1] * leftover_sla

            # 5c. Loop through the active LinkedIn archetypes and generate campaigns for each
            for index, archetype in enumerate(linkedin_archetypes):

                # 5d. Check if the current archetype is in "template mode." Non-template mode archetypes require a non-expiring CTA
                ctas = []
                if not archetype.template_mode:
                    #  Get CTAs for archetype. If none, block and send slack message
                    ctas: list[GeneratedMessageCTA] = GeneratedMessageCTA.query.filter(
                        GeneratedMessageCTA.archetype_id == archetype.id,
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

                # 5e. Use the sla_count to get the number of prospects to generate
                # Check that there are enough prospects to generate the campaign
                num_to_generate = sla_counts[index]
                num_available_prospects = len(
                    smart_get_prospects_for_campaign(
                        archetype.id,
                        num_to_generate,
                        GeneratedMessageType.LINKEDIN,
                    )
                )
                if num_to_generate <= num_available_prospects:
                    # Create the campaign
                    oc = create_outbound_campaign(
                        prospect_ids=[],
                        num_prospects=num_to_generate,
                        campaign_type=GeneratedMessageType.LINKEDIN,
                        client_archetype_id=archetype.id,
                        client_sdr_id=client_sdr.id,
                        campaign_start_date=start_date,
                        campaign_end_date=end_date,
                        ctas=[cta.id for cta in ctas],
                        is_daily_generation=daily
                    )
                    if not oc:
                        send_slack_message(
                            f"🤖 ❌ ❓ AUTOPILOT LINKEDIN: Campaign not created for {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.archetype}.",
                            [SLACK_CHANNEL],
                        )
                    # Generate the campaign
                    else:
                        generating = generate_campaign(oc.id)
                        if not generating:
                            send_slack_message(
                                f"🤖 ❌ ❓ AUTOPILOT LINKEDIN: Error queuing messages for generation. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.archetype}.",
                                [SLACK_CHANNEL],
                            )
                        else:
                            linkedin_campaigns_generated.append(archetype.archetype)
                else:
                    send_slack_message(
                        f"🤖 ❌ 🧑‍🤝‍🧑 AUTOPILOT LINKEDIN: Not enough prospects to generate. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.archetype}.",
                        [SLACK_CHANNEL],
                    )

        # 6. Generate campaign for Email given SLAs for the SDR
        # TODO: GET PARITY WITH ABOVE WHEN UNCOMMENTED
        if (
            sla_schedule.email_volume > 0 and False
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

        # 7. Send appropriate slack messages
        if len(linkedin_campaigns_generated) == 0 and len(email_campaigns_generated) == 0:
            return (
                False,
                f"Autopilot Campaign not created for {client_sdr.name} (#{client_sdr.id}): Neither Email nor LinkedIn generated.",
            )
        send_slack_message(
            f"🤖 ✅ Autopilot Campaign successfully generated: {client_sdr.name} (#{client_sdr.id}).\n*LinkedIn:* {linkedin_campaigns_generated}\n*Email:* {email_campaigns_generated}",
            [SLACK_CHANNEL],
        )

        return (
            True,
            f"Autopilot Campaign successfully queued for generation: {client_sdr.name} (#{client_sdr.id}).\nLinkedIn: {linkedin_campaigns_generated}\nEmail: {email_campaigns_generated}",
        )
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def get_available_sla_count(
    client_sdr_id: int,
    campaign_type: GeneratedMessageType,
    start_date: Optional[date],
    per_day: bool = False,
) -> tuple[int, str]:
    """Gets the available SLA count for a given week and campaign type.

    The SLA count is calculated by determining the number of prospects in campaigns that are scheduled
    to start on the provided start_date, less the SLA in the SLA Schedule for the SDR.

    Note: The start_date will be transformed to the monday and friday of the week of the start_date.

    Args:
        client_sdr_id (int): The ID of the SDR
        campaign_type (GeneratedMessageType): The type of campaign
        start_date (Optional[datetime.date], optional): The start date. Defaults to datetime.date.today().

    Returns:
        tuple[int, int, str]: The available SLA count, the total SLA count, and an error message if there is one.
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    start_date = start_date or datetime.today()
    tomorrow = start_date + timedelta(days=1)

    monday, sunday = get_current_monday_sunday(start_date)

    # Get campaigns that are marked as starting on the provided date
    campaigns: list[OutboundCampaign] = OutboundCampaign.query.filter(
        OutboundCampaign.client_sdr_id == client_sdr_id,
        OutboundCampaign.campaign_type == campaign_type,
        OutboundCampaign.status != OutboundCampaignStatus.CANCELLED,
        func.date(OutboundCampaign.campaign_start_date) >= monday,
        func.date(OutboundCampaign.campaign_end_date) <= sunday,
    ).all()

    # Count the number of prospects in each campaign
    num_prospects = 0
    for campaign in campaigns:
        num_prospects += len(campaign.prospect_ids)

    # Get the SLA Schedule entry for this date range
    sla_schedule: SLASchedule = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id,
        func.date(SLASchedule.start_date) >= monday,
        func.date(SLASchedule.end_date) <= sunday,
    ).first()
    if not sla_schedule:
        return -1, -1, f"No SLA Schedule entry for SDR '{sdr.name}' between {monday} - {sunday}."

    # Return the difference between the SLA and the number of prospects in campaigns
    try:
        start_date = start_date.date()
        tomorrow = tomorrow.date()
    except:
        pass

    if campaign_type == GeneratedMessageType.LINKEDIN:
        if per_day:
            # Get Campaign that starts today and ends tomorrow and is a daily generation
            campaign: OutboundCampaign = OutboundCampaign.query.filter(
                OutboundCampaign.client_sdr_id == client_sdr_id,
                OutboundCampaign.campaign_type == campaign_type,
                OutboundCampaign.status != OutboundCampaignStatus.CANCELLED,
                func.date(OutboundCampaign.campaign_start_date) == start_date,
                func.date(OutboundCampaign.campaign_end_date) == tomorrow,
                OutboundCampaign.is_daily_generation == True,
            ).first()
            if campaign:
                return -1, -1, f"Daily SLA for LinkedIn has been filled for SDR '{sdr.name}' between {monday} - {sunday}."

            return sla_schedule.linkedin_volume // 5, sla_schedule.linkedin_volume, ""

        if sla_schedule.linkedin_volume < num_prospects:
            return -1, -1, f"SLA for LinkedIn has been filled for SDR '{sdr.name}' between {monday} - {sunday}."

        return sla_schedule.linkedin_volume - num_prospects, sla_schedule.linkedin_volume, ""
    elif campaign_type == GeneratedMessageType.EMAIL:
        if per_day:
            # Get Campaign that starts today and ends tomorrow and is a daily generation
            campaign: OutboundCampaign = OutboundCampaign.query.filter(
                OutboundCampaign.client_sdr_id == client_sdr_id,
                OutboundCampaign.campaign_type == campaign_type,
                OutboundCampaign.status != OutboundCampaignStatus.CANCELLED,
                func.date(OutboundCampaign.campaign_start_date) == start_date,
                func.date(OutboundCampaign.campaign_end_date) == tomorrow,
                OutboundCampaign.is_daily_generation == True,
            ).first()
            if campaign:
                return -1, -1, f"Daily SLA for Email has been filled for SDR '{sdr.name}' between {monday} - {sunday}."
            return sla_schedule.email_volume // 5, sla_schedule.email_volume, ""

        if sla_schedule.email_volume < num_prospects:
            return -1, -1, f"SLA for Email has been filled for SDR '{sdr.name}' between {monday} - {sunday}."

        return sla_schedule.email_volume - num_prospects, sla_schedule.email_volume, ""

    return -1, -1, f"Something went wrong. This should never happen."
