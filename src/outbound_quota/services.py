from app import db, celery
import datetime
from src.client.models import Client, ClientArchetype, ClientSDR, SLASchedule

from src.outbound_quota.models import OutboundQuotaSnapshot


@celery.task
def capture_outbound_quota_snapshot() -> OutboundQuotaSnapshot:
    """Capture the current outbound quota and store it in the database.

    Returns:
        OutboundQuotaSnapshot: The snapshot that was created
    """
    # Get the current date
    date = datetime.date.today()

    # If it is the weekend, The snapshot should just be 0s for the time being
    if date.weekday() in [5, 6]:
        weekend_snapshot = OutboundQuotaSnapshot(
            date=date,
            total_linkedin_quota=0,
            total_email_quota=0,
            meta_data={"note": "Weekend, no outbound quota."},
        )
        db.session.add(weekend_snapshot)
        db.session.commit()
        return weekend_snapshot

    meta_data = {}

    # Get active clients
    active_clients: list[Client] = Client.query.filter(
        Client.active == True, Client.id != 1
    ).all()
    active_sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True,
        ClientSDR.client_id.in_([client.id for client in active_clients]),
    ).all()

    # LINKEDIN QUOTA
    # Get the active Archetypes for LinkedIn
    linkedin_quota = 0
    active_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.active == True,
        ClientArchetype.linkedin_active == True,
        ClientArchetype.client_sdr_id.in_([sdr.id for sdr in active_sdrs]),
    ).all()
    linkedin_sdrs = set()
    for archetype in active_archetypes:
        # Don't double count SLAs
        if archetype.client_sdr_id in linkedin_sdrs:
            continue
        linkedin_sdrs.add(archetype.client_sdr_id)

        # Get the SDR
        sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)

        # Exclude SDRs that have an invalid LinkedIn token
        if sdr.li_at_token is None or sdr.li_at_token == "INVALID":
            continue

        # Get the SLASchedule for this SDR for this week
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == sdr.id,
            SLASchedule.start_date <= date,
            SLASchedule.end_date >= date,
        ).first()

        # Add the linkedin_volume to the quota (but we need to divide by 5)
        linkedin_quota += sla_schedule.linkedin_volume / 5

        key = f"{sdr.name} (#{sdr.id})"
        if key not in meta_data:
            meta_data[key] = {}
        meta_data[key]["linkedin_volume"] = sla_schedule.linkedin_volume / 5

    # EMAIL QUOTA
    # Get the active Archetypes for Email
    email_quota = 0
    active_archetypes = ClientArchetype.query.filter(
        ClientArchetype.active == True,
        ClientArchetype.email_active == True,
        ClientArchetype.client_sdr_id.in_([sdr.id for sdr in active_sdrs]),
    ).all()
    email_sdrs = set()
    for archetype in active_archetypes:
        # Don't double count SLAs
        if archetype.client_sdr_id in email_sdrs:
            continue
        email_sdrs.add(archetype.client_sdr_id)

        # Get the SDR
        sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)

        # Get the SLASchedule for this SDR for this week
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == sdr.id,
            SLASchedule.start_date <= date,
            SLASchedule.end_date >= date,
        ).first()

        # Add the email_volume to the quota
        email_quota += sla_schedule.email_volume / 5

        key = f"{sdr.name} (#{sdr.id})"
        if key not in meta_data:
            meta_data[key] = {}
        meta_data[key]["email_volume"] = sla_schedule.email_volume / 5

    print(linkedin_quota)
    print(email_quota)
    print(meta_data)

    # Create the snapshot
    snapshot = OutboundQuotaSnapshot(
        date=date,
        total_linkedin_quota=linkedin_quota,
        total_email_quota=email_quota,
        meta_data=meta_data,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot
