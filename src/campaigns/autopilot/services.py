from app import db, celery
from model_import import (
    Prospect,
    Client,
    ClientSDR,
    ClientArchetype,
    GeneratedMessageType,
    GeneratedMessageCTA,
    GeneratedMessage,
    GeneratedMessageStatus,
    OutboundCampaign,
    OutboundCampaignStatus,
)
from tqdm import tqdm
from src.ai_requests.models import AIRequest
from src.ai_requests.services import create_ai_requests
from src.analytics.models import AutoDeleteMessageAnalytics
from src.client.models import SLASchedule
from src.email_outbound.models import ProspectEmail
from src.utils.datetime.dateparse_utils import convert_string_to_datetime
from src.utils.slack import send_slack_message, URL_MAP
from src.utils.datetime.dateutils import (
    get_current_monday_sunday,
    get_next_next_monday_sunday,
)
from src.campaigns.services import (
    create_outbound_campaign,
    generate_campaign,
    mark_campaign_as_initial_review_complete,
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
    li_clients: list[Client] = Client.query.filter(
        Client.active == True,
        Client.auto_generate_li_messages == True,
    ).all()
    client_ids = [client.id for client in li_clients]

    # Get all SDRs for each client that has auto_generate_li_messages
    li_sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.client_id.in_(client_ids), ClientSDR.active == True
    ).all()

    # Get active clients that have auto_generate_email_messages enabled
    email_clients: list[Client] = Client.query.filter(
        Client.active == True,
        Client.auto_generate_email_messages == True,
    ).all()

    # Get all SDRs for each client that has auto_generate_email_messages
    email_sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.client_id.in_([client.id for client in email_clients]),
        ClientSDR.active == True,
    ).all()

    # Generate LI campaigns for SDRs, using another function
    for li_sdr in li_sdrs:
        li_sdr_id = li_sdr.id
        daily_generate_linkedin_campaign_for_sdr.apply_async(args=[li_sdr_id])

    # Generate Email campaigns for SDRs, using another function
    for email_sdr in email_sdrs:
        email_sdr_id = email_sdr.id
        daily_generate_email_campaign_for_sdr.apply_async(args=[email_sdr_id])


@celery.task(bind=True, max_retries=1)
def daily_generate_linkedin_campaign_for_sdr(
    self,
    client_sdr_id: int,
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
                f"🤖 ❌ 🧑‍🤝‍🧑 Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}). No active LinkedIn archetypes.",
                [SLACK_CHANNEL],
            )
            return (
                False,
                f"Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}): No active LinkedIn archetypes",
            )

        # 2. Get the start dates
        start_date = datetime.today()
        end_date = start_date + timedelta(days=1)

        # 3. Get the SLA Schedule entry for this date range
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr.id,
            func.date(SLASchedule.start_date) <= start_date,
            func.date(SLASchedule.end_date) >= end_date,
        ).first()
        if not sla_schedule:
            send_slack_message(
                f"🤖 ❌ 📅 Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}). No SLA Schedule entry for {start_date}.",
                [SLACK_CHANNEL],
            )
            return (
                False,
                f"Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}): No SLA Schedule entry for {start_date}",
            )

        # 4. Campaigns generated will track which campaigns have been generated
        linkedin_campaigns_generated = []

        # 5. Generate campaign for LinkedIn given SLAs for the SDR
        if sla_schedule.linkedin_volume > 0:
            # 5a. Get current date and date 10 days from now
            current_date = datetime.utcnow()

            # 5a. Get the available SLA count for this SDR
            available_sla, total_sla, message = get_available_sla_count(
                client_sdr_id=client_sdr_id,
                campaign_type=GeneratedMessageType.LINKEDIN,
                start_date=start_date,
                per_day=True,
            )
            if available_sla == -1:
                send_slack_message(
                    f"🤖 ❌ 📅 Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}). {message}",
                    [SLACK_CHANNEL],
                )
                return (
                    False,
                    f"Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}): {message}",
                )

            # Increase SLA by 25% and round up
            available_sla = int(available_sla * 1.25)

            sla_per_campaign = available_sla // len(linkedin_archetypes)
            leftover_sla = available_sla % len(linkedin_archetypes)

            # 5b. Create a list of SLA counts for each archetype.
            # Example: 90 SLA, 3 archetypes -> [30, 30, 30]. 90 SLA, 4 archetypes -> [22, 22, 23, 23]
            sla_counts = [sla_per_campaign] * (
                len(linkedin_archetypes) - leftover_sla
            ) + [sla_per_campaign + 1] * leftover_sla

            # 5c. Loop through the active LinkedIn archetypes and generate campaigns for each
            for index, archetype in enumerate(linkedin_archetypes):
                # 5d. Check if the current archetype is in "template mode." Non-template mode archetypes require a non-expiring CTA
                ctas = []
                if not archetype.template_mode:
                    in_10_days = current_date + timedelta(days=10)

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
                            f"🤖 ❌ 🖊️ Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}). No active CTAs for LinkedIn.",
                            [SLACK_CHANNEL],
                        )
                        return (
                            False,
                            f"Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}): No active CTAs for LinkedIn",
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
                    is_daily_generation=True,
                )
                if not oc:
                    send_slack_message(
                        f"🤖 ❌ ❓ Daily Campaign (LI): Campaign not created for {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                        [SLACK_CHANNEL],
                    )
                # Generate the campaign
                else:
                    generating = generate_campaign(oc.id)
                    if not generating:
                        send_slack_message(
                            f"🤖 ❌ ❓ Daily Campaign (LI): Error queuing messages for generation. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                            [SLACK_CHANNEL],
                        )
                    else:
                        linkedin_campaigns_generated.append(archetype.archetype)

        # 6. Send appropriate slack messages
        if len(linkedin_campaigns_generated) == 0:
            return (
                False,
                f"Daily Campaign (LI) not created for {client_sdr.name} (#{client_sdr.id}): No LinkedIn campaigns generated.",
            )
        send_slack_message(
            f"🤖 ✅ 🧑‍🤝‍🧑 Daily Campaign (LI) created for {client_sdr.name} (#{client_sdr.id}).",
            webhook_urls=[SLACK_CHANNEL],
        )

        return (
            True,
            f"Daily Campaign (LI) created for {client_sdr.name} (#{client_sdr.id}).",
        )
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=1)
def daily_generate_email_campaign_for_sdr(
    self,
    client_sdr_id: int,
) -> tuple[bool, str]:
    try:
        # Get SDR
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        # 1. Get the active Email archetypes
        email_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == client_sdr.id,
            ClientArchetype.active == True,
            ClientArchetype.email_active == True,
        ).all()
        if len(email_archetypes) == 0:
            send_slack_message(
                f"🤖 ❌ 🧑‍🤝‍🧑 Daily Campaign (Email) not created for {client_sdr.name} (#{client_sdr.id}). No active Email archetypes.",
                [SLACK_CHANNEL],
            )
            return (
                False,
                f"Daily Campaign (Email) not created for {client_sdr.name} (#{client_sdr.id}): No active Email archetypes",
            )

        # 2. Get the start dates
        start_date = datetime.today()
        end_date = start_date + timedelta(days=1)

        # 3. Get the SLA Schedule entry for this date range
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr.id,
            func.date(SLASchedule.start_date) <= start_date,
            func.date(SLASchedule.end_date) >= end_date,
        ).first()
        if not sla_schedule:
            send_slack_message(
                f"🤖 ❌ 📅 Daily Campaign (Email) not created for {client_sdr.name} (#{client_sdr.id}). No SLA Schedule entry for {start_date}.",
                [SLACK_CHANNEL],
            )
            return (
                False,
                f"Daily Campaign (Email) not created for {client_sdr.name} (#{client_sdr.id}): No SLA Schedule entry for {start_date}",
            )

        # 4. Campaigns generated will track which campaigns have been generated
        email_campaigns_generated = []

        # 5. Generate campaign for Email given SLAs for the SDR
        if sla_schedule.email_volume > 0:
            # 5a. Get the available SLA count for this SDR
            available_sla, total_sla, message = get_available_sla_count(
                client_sdr_id=client_sdr_id,
                campaign_type=GeneratedMessageType.EMAIL,
                start_date=start_date,
                per_day=True,
            )
            if available_sla == -1:
                send_slack_message(
                    f"🤖 ❌ 📅 Daily Campaign (Email) not created for {client_sdr.name} (#{client_sdr.id}). {message}",
                    [SLACK_CHANNEL],
                )
                return (
                    False,
                    f"Daily Campaign (Email) not created for {client_sdr.name} (#{client_sdr.id}): {message}",
                )

            # Increase SLA by 25% and round up
            available_sla = int(available_sla * 1.25)

            sla_per_campaign = available_sla // len(email_archetypes)
            leftover_sla = available_sla % len(email_archetypes)

            # 5b. Create a list of SLA counts for each archetype.
            # Example: 90 SLA, 3 archetypes -> [30, 30, 30]. 90 SLA, 4 archetypes -> [22, 22, 23, 23]
            sla_counts = [sla_per_campaign] * (len(email_archetypes) - leftover_sla) + [
                sla_per_campaign + 1
            ] * leftover_sla

            # 5c. Loop through the active Email archetypes and generate campaigns for each
            for index, archetype in enumerate(email_archetypes):
                # 5d. Use the sla_count to get the number of prospects to generate
                # Check that there are enough prospects to generate the campaign
                num_to_generate = min(sla_counts[index], 500)
                num_available_prospects = len(
                    smart_get_prospects_for_campaign(
                        archetype.id,
                        num_to_generate,
                        GeneratedMessageType.EMAIL,
                    )
                )
                if num_available_prospects == 0 or num_to_generate == 0:
                    send_slack_message(
                        f"🤖 ❌ 🧑‍🤝‍🧑 Daily Campaign (Email): No prospects to generate. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                        [SLACK_CHANNEL],
                    )
                    continue
                if num_available_prospects > 0:
                    # Create the campaign
                    oc = create_outbound_campaign(
                        prospect_ids=[],
                        num_prospects=num_to_generate,
                        campaign_type=GeneratedMessageType.EMAIL,
                        client_archetype_id=archetype.id,
                        client_sdr_id=client_sdr.id,
                        campaign_start_date=start_date,
                        campaign_end_date=end_date,
                        is_daily_generation=True,
                    )
                    if not oc:
                        send_slack_message(
                            f"🤖 ❌ ❓ Daily Campaign (Email): Campaign not created for {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                            [SLACK_CHANNEL],
                        )
                    # Generate the campaign
                    else:
                        generating = generate_campaign(oc.id)
                        if not generating:
                            send_slack_message(
                                f"🤖 ❌ ❓ Daily Campaign (Email): Error queuing messages for generation. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                                [SLACK_CHANNEL],
                            )
                        else:
                            email_campaigns_generated.append(archetype.archetype)
                else:
                    send_slack_message(
                        f"🤖 ❌ 🧑‍🤝‍🧑 Daily Campaign (Email): Not enough prospects to generate. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                        [SLACK_CHANNEL],
                    )

        # 6. Send appropriate slack messages
        if len(email_campaigns_generated) == 0:
            return (
                False,
                f"Daily Campaign (Email) not created for {client_sdr.name} (#{client_sdr.id}): No Email campaigns generated.",
            )
        send_slack_message(
            f"🤖 ✅ 🧑‍🤝‍🧑 Daily Campaign (Email) created for {client_sdr.name} (#{client_sdr.id}).",
            webhook_urls=[SLACK_CHANNEL],
        )

        return (
            True,
            f"Daily Campaign (Email) created for {client_sdr.name} (#{client_sdr.id}).",
        )
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=1)
def collect_and_generate_autopilot_campaign_for_sdr(
    self,
    client_sdr_id: int,
    custom_start_date: Optional[datetime] = None,
    daily: bool = False,  # TECHNICALLY DEPRECATED, REMOVE IN FUTURE AFTER 12/20/2023
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
        start_date, end_date = get_next_next_monday_sunday(datetime.today())

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
        if sla_schedule.linkedin_volume > 0:
            # 5a. Get current date and date 10 days from now
            current_date = datetime.utcnow()
            in_10_days = current_date + timedelta(days=10)

            # 5a. Get the available SLA count for this SDR
            available_sla, total_sla, message = get_available_sla_count(
                client_sdr_id=client_sdr_id,
                campaign_type=GeneratedMessageType.LINKEDIN,
                start_date=start_date,
                per_day=daily,
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

            # increase SLA by 25% and round up
            available_sla = int(available_sla * 1.25)

            sla_per_campaign = available_sla // len(linkedin_archetypes)
            leftover_sla = available_sla % len(linkedin_archetypes)

            # 5b. Create a list of SLA counts for each archetype.
            # Example: 90 SLA, 3 archetypes -> [30, 30, 30]. 90 SLA, 4 archetypes -> [22, 22, 23, 23]
            sla_counts = [sla_per_campaign] * (
                len(linkedin_archetypes) - leftover_sla
            ) + [sla_per_campaign + 1] * leftover_sla

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
                        is_daily_generation=daily,
                    )
                    if not oc:
                        send_slack_message(
                            f"🤖 ❌ ❓ AUTOPILOT LINKEDIN: Campaign not created for {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                            [SLACK_CHANNEL],
                        )
                    # Generate the campaign
                    else:
                        generating = generate_campaign(oc.id)
                        if not generating:
                            send_slack_message(
                                f"🤖 ❌ ❓ AUTOPILOT LINKEDIN: Error queuing messages for generation. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                                [SLACK_CHANNEL],
                            )
                        else:
                            linkedin_campaigns_generated.append(archetype.archetype)
                else:
                    send_slack_message(
                        f"🤖 ❌ 🧑‍🤝‍🧑 AUTOPILOT LINKEDIN: Not enough prospects to generate. {client_sdr.name} (#{client_sdr.id}). Persona: {archetype.emoji} {archetype.archetype}.",
                        [SLACK_CHANNEL],
                    )

        # 6. Generate campaign for Email given SLAs for the SDR
        # TODO: GET PARITY WITH ABOVE WHEN UNCOMMENTED
        if sla_schedule.email_volume > 0 and False:  # Email
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
        if (
            len(linkedin_campaigns_generated) == 0
            and len(email_campaigns_generated) == 0
        ):
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
) -> tuple[int, int, str]:
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
        return (
            -1,
            -1,
            f"No SLA Schedule entry for SDR '{sdr.name}' between {monday} - {sunday}.",
        )

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
                return (
                    -1,
                    -1,
                    f"Daily SLA for LinkedIn has been filled.",
                )

            return sla_schedule.linkedin_volume // 5, sla_schedule.linkedin_volume, ""

        if sla_schedule.linkedin_volume < num_prospects:
            return (
                -1,
                -1,
                f"SLA for LinkedIn has been filled for SDR '{sdr.name}' between {monday} - {sunday}.",
            )

        return (
            sla_schedule.linkedin_volume - num_prospects,
            sla_schedule.linkedin_volume,
            "",
        )
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
                return (
                    -1,
                    -1,
                    f"Daily SLA for Email has been filled",
                )
            return sla_schedule.email_volume // 5, sla_schedule.email_volume, ""

        if sla_schedule.email_volume < num_prospects:
            return (
                -1,
                -1,
                f"SLA for Email has been filled for SDR '{sdr.name}' between {monday} - {sunday}.",
            )

        return sla_schedule.email_volume - num_prospects, sla_schedule.email_volume, ""

    return -1, -1, f"Something went wrong. This should never happen."


def auto_send_campaign(campaign_id: int):
    HOURS_AGO = 4
    COMPLETE_THRESHOLD = 0.95
    SUCCESS_THRESHOLD = 0.75

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    messages: list[GeneratedMessage] = GeneratedMessage.query.filter(
        GeneratedMessage.outbound_campaign_id == campaign_id,
        GeneratedMessage.message_status != GeneratedMessageStatus.DRAFT,
    ).all()
    sdr: ClientSDR = ClientSDR.query.get(campaign.client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(campaign.client_archetype_id)
    campaign_type = campaign.campaign_type

    # Check that auto-send is enabled
    if campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        if not sdr.auto_send_linkedin_campaign:
            send_slack_message(
                f"❌ ({campaign_type.value}) Campaign #{campaign.id} for {sdr.name} has been blocked for the `{archetype.archetype}` persona.\nReason: Auto-send is not enabled for LinkedIn campaigns.\n\nSolution: Enable auto-send for LinkedIn campaigns.",
                [URL_MAP["ops-auto-send-campaign"]],
            )
            return False
    elif campaign.campaign_type == GeneratedMessageType.EMAIL:
        if not sdr.auto_send_email_campaign:
            send_slack_message(
                f"❌ ({campaign_type.value}) Campaign #{campaign.id} for {sdr.name} has been blocked for the `{archetype.archetype}` persona.\nReason: Auto-send is not enabled for Email campaigns.\n\nSolution: Enable auto-send for Email campaigns.",
                [URL_MAP["ops-auto-send-campaign"]],
            )
            return False

    # Check if campaign was created at least 4 hours ago
    if campaign.created_at + timedelta(hours=HOURS_AGO) > datetime.utcnow():
        # Get the campaign type
        send_slack_message(
            f"❌ ({campaign_type.value}) Campaign #{campaign.id} for {sdr.name} has been blocked for the `{archetype.archetype}` persona.\nReason: Campaign was created less than {HOURS_AGO} hours ago.\n\nSolution: Wait until the campaign is at least {HOURS_AGO} hours old before sending.",
            [URL_MAP["ops-auto-send-campaign"]],
        )
        return False

    # Check if 95% of the messages have been generated
    # num_generated = len([message for message in messages if message.message_status != GeneratedMessageStatus.DRAFT])
    # if num_generated / len(messages) < COMPLETE_THRESHOLD:
    #     send_slack_message(
    #         f"❌ Campaign #{campaign.id} for {sdr.name} has been blocked for the `{archetype.archetype}` persona.\nReason: Not all the generations in this campaign are complete.\n\nSolution: Solution: Manually inspect the campaign. Relay relevant details to engineers for fix.",
    #         [URL_MAP["ops-auto-send-campaign"]],
    #     )
    #     return False

    # Check if 75% of the messages have been approved
    num_approved = len([message for message in messages if message.ai_approved])
    if len(messages) > 0 and num_approved / len(messages) < SUCCESS_THRESHOLD:
        percentage_failed = round(((1 - (num_approved / len(messages))) * 100), 1)
        send_slack_message(
            f"🟡 ({campaign_type.value}) Campaign #{campaign.id} warning for {sdr.name} for the `{archetype.archetype}` persona.\nReason: {percentage_failed}% of generations had errors.\n\nSolution: Manually review & send the messages. Relay relevant details to engineers for fix.",
            [URL_MAP["ops-auto-send-campaign"]],
        )

        # Create an AI Request Card if there is none
        title = f"Review Blocked Campaign `{archetype.archetype}`(#{archetype.id})"
        ai_request_exists: AIRequest = AIRequest.query.filter(
            AIRequest.client_sdr_id == sdr.id,
            AIRequest.title == title,
        ).first()
        if not ai_request_exists:
            campaign_link = f"https://sellscale.retool.com/embedded/public/eb93cfac-cfed-4d65-b45f-459ffc546bce#campaign_uuid={campaign.uuid}"
            create_ai_requests(
                client_sdr_id=sdr.id,
                description=f"`{archetype.archetype}` had {percentage_failed}% of generations with errors. Please review and manually approve or flag any issues with rule engine. Review here: {campaign_link}",
                title=title,
                days_till_due=1,
            )

        return False

    # Remove prospects that aren't approved
    approved_prospect_ids = [
        message.prospect_id for message in messages if message.ai_approved
    ]
    # Turn into a set list to remove duplicates
    approved_prospect_ids = list(set(approved_prospect_ids))
    campaign.prospect_ids = approved_prospect_ids
    db.session.commit()

    # Get the invalid message prospect ID and message IDs
    invalid_prospect_ids: list[int] = [
        message.prospect_id
        for message in messages
        if not message.ai_approved
        and (message.blocking_problems and len(message.blocking_problems) > 0)
    ]
    invalid_message_ids: list[int] = [
        message.id
        for message in messages
        if not message.ai_approved
        and (message.blocking_problems and len(message.blocking_problems) > 0)
    ]
    # Turn into a set list to remove duplicates
    invalid_prospect_ids = list(set(invalid_prospect_ids))
    invalid_message_ids = list(set(invalid_message_ids))

    # Log the bad messages before we wipe them
    for message_id in invalid_message_ids:
        message: GeneratedMessage = GeneratedMessage.query.get(message_id)
        auto_delete_message_log = AutoDeleteMessageAnalytics(
            message_to_dict=message.to_dict(),
            problem=message.problems,
            sdr_name=sdr.name,
            message=message.completion,
            send_date=datetime.utcnow(),
            channel=message.message_type.value,
        )
        db.session.add(auto_delete_message_log)
    db.session.commit()

    from src.research.linkedin.services import (
        reset_batch_of_prospect_research_and_messages,
    )

    if campaign_type == GeneratedMessageType.LINKEDIN:
        reset_batch_of_prospect_research_and_messages(
            prospect_ids=invalid_prospect_ids, use_celery=False
        )
    elif campaign_type == GeneratedMessageType.EMAIL:
        # Get the generated messages and set them all to BLOCKED
        for prospect_id in invalid_prospect_ids:
            prospect: Prospect = Prospect.query.get(prospect_id)
            prospect_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )
            subject_line: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_subject_line
            )
            body: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_body
            )
            subject_line.message_status = GeneratedMessageStatus.BLOCKED
            body.message_status = GeneratedMessageStatus.BLOCKED
        db.session.commit()

    # Send the campaign
    mark_campaign_as_initial_review_complete(campaign_id=campaign_id)

    return True


def send_slack_message_for_invalid_messages(
    message_ids: list[int], campaign_type: GeneratedMessageType
):
    messages: list[GeneratedMessage] = GeneratedMessage.query.filter(
        GeneratedMessage.id.in_(message_ids)
    ).all()

    for message in messages:
        prospect_id = message.prospect_id
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

        problems = "\n- ".join(message.problems)

        # We should combine the problems from the subject line and body
        # This ensures we don't send "null" if one of the two is empty
        if not message.problems and message.message_type == GeneratedMessageType.EMAIL:
            prospect: Prospect = Prospect.query.get(message.prospect_id)
            prospect_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )
            subject_line: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_subject_line
            )
            body: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_body
            )
            problems = ""
            if subject_line.problems:
                problems += "\n- ".join(subject_line.problems)
            elif body.problems:
                problems += "\n- ".join(body.problems)

        send_slack_message(
            f"🗑 {campaign_type.value} *Auto-Deleted Message During Autosend for {client_sdr.name}*\n*Prospect:* `{prospect.full_name}`\n*Message:*\n```{message.completion}```\n*Problems:* \n`- {problems}`",
            [URL_MAP["ops-auto-send-auto-deleted-messages"]],
        )

        m: GeneratedMessage = message

        auto_delete_message_log = AutoDeleteMessageAnalytics(
            problem=problems,
            prospect=prospect.full_name,
            sdr_name=client_sdr.name,
            message=message.completion,
            send_date=datetime.utcnow(),
            channel=m.message_type.value,
        )
        db.session.add(auto_delete_message_log)
        db.session.commit()


@celery.task(bind=True, max_retries=3)
def auto_send_campaigns_and_send_approved_messages_job(self):
    try:
        auto_send_all_campaigns()
        send_approved_messages_in_complete_campaigns()
    except Exception as e:
        send_slack_message(
            f"❌ Error in auto_send_campaigns_and_send_approved_messages_job: {e}",
            [URL_MAP["ops-auto-send-campaign"]],
        )
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def auto_send_all_campaigns():
    query = f"""
with d as (
	SELECT
		s.name sdr_name,
		c.id campaign_id,
		c.name campaign_name,
		c.status campaign_status,
		c.campaign_start_date generation_date,
		c.campaign_end_date approval_date,
		c.prospect_ids prospect_ids,
		c.uuid campaign_uuid,
		count(array_length(g.problems, 1) > 0)
	FROM
		outbound_campaign AS c
		LEFT JOIN client_sdr AS s ON c.client_sdr_id = s.id
		LEFT JOIN generated_message AS g ON g.prospect_id = ANY (c.prospect_ids)
	WHERE
		c.is_daily_generation = TRUE
		AND c.status <> 'COMPLETE'
		AND g.message_status = 'APPROVED'
	GROUP BY
		1,
		2
) select array_agg(campaign_id) from d;
    """

    campaign_ids = db.session.execute(query).fetchone()[0]
    if not campaign_ids:
        return False

    for campaign_id in campaign_ids:
        print(f"Sending campaign #{campaign_id}...")
        auto_send_campaign(campaign_id)

    return True


def send_approved_messages_in_complete_campaigns():
    query = """
        with d as (
            select
                generated_message.id,
                prospect.status,
                generated_message.message_status,
                client_sdr.name,
                generated_message.completion
            from outbound_campaign
                join prospect on prospect.id = any(outbound_campaign.prospect_ids)
                join generated_message on generated_message.id = prospect.approved_outreach_message_id
                join client_sdr on client_sdr.id = prospect.client_sdr_id
            where outbound_campaign.created_at > NOW() - '128 hours'::INTERVAL
                and outbound_campaign.status = 'COMPLETE'
                and message_status not in ('SENT', 'QUEUED_FOR_OUTREACH', 'FAILED_TO_SEND', 'DRAFT')
                and prospect.status not in ('PROSPECTED')
        )
        select *
        from d;
    """

    data = db.session.execute(query).fetchall()

    for row in tqdm(data):
        generated_message = GeneratedMessage.query.get(row[0])

        generated_message.message_status = GeneratedMessageStatus.QUEUED_FOR_OUTREACH
        db.session.add(generated_message)
        db.session.commit()
