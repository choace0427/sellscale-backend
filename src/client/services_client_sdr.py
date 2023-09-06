from datetime import datetime
from typing import Optional
from app import db, celery
from sqlalchemy import or_

from src.client.models import Client, ClientSDR, LinkedInSLAChange, WarmupScheduleLinkedIn
from src.utils.slack import send_slack_message, URL_MAP

def update_sdr_blacklist_words(client_sdr_id: int, blacklist_words: list[str]) -> bool:
    """Updates the blacklist_words field for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        bool: True if successful, False otherwise
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    sdr.blacklisted_words = blacklist_words
    db.session.commit()

    return True


def get_sdr_blacklist_words(client_sdr_id: int) -> list[str]:
    """Gets the blacklist_words field for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        list[str]: The blacklist_words field for the Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    return sdr.blacklisted_words


def create_warmup_schedule_linkedin(
    client_sdr_id: int,
    week_0_sla: int = None,
    week_1_sla: int = None,
    week_2_sla: int = None,
    week_3_sla: int = None,
    week_4_sla: int = None,
) -> int:
    """ Creates a Warmup Schedule for LinkedIn

    Args:
        client_sdr_id (int): The id of the Client SDR
        week_0_sla (int, optional): The SLA for week 0 . Defaults to None.
        week_1_sla (int, optional): The SLA for week 1 . Defaults to None.
        week_2_sla (int, optional): The SLA for week 2 . Defaults to None.
        week_3_sla (int, optional): The SLA for week 3 . Defaults to None.
        week_4_sla (int, optional): The SLA for week 4 . Defaults to None.

    Returns:
        int: The id of the Warmup Schedule
    """
    # Get the SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    # Create the Warmup Schedule
    warmup_schedule: WarmupScheduleLinkedIn = WarmupScheduleLinkedIn(
        client_sdr_id=client_sdr_id,
        week_0_sla=week_0_sla,
        week_1_sla=week_1_sla,
        week_2_sla=week_2_sla,
        week_3_sla=week_3_sla,
        week_4_sla=week_4_sla,
    )
    db.session.add(warmup_schedule)
    db.session.commit()

    # IF all the SLAs are None, then we set the SLAs to the conservative schedule
    if not any([week_0_sla, week_1_sla, week_2_sla, week_3_sla, week_4_sla]):
        warmup_schedule.set_conservative_schedule()

    return warmup_schedule.id


@celery.task(bind=True, max_retries=3)
def auto_update_sdr_linkedin_sla_task():
    """Updates the LinkedIn SLA for all active SDRs, if applicable. This task is run every 24 hours."""
    # Get the IDs of all active Clients
    active_client_ids: list[int] = [client.id for client in Client.query.filter_by(active=True).all()]

    # Get all active SDRs that do not have warmup LinkedIn complete
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active==True,
        or_(
            ClientSDR.warmup_linkedin_complete==False,
            ClientSDR.warmup_linkedin_complete==None
        ),
        ClientSDR.client_id.in_(active_client_ids)
    ).all()

    # Update the LinkedIn SLA for each SDR
    for sdr in sdrs:
        old_sla = sdr.weekly_li_outbound_target

        # Get the most recent LinkedIn warmup status change record
        most_recent_sla_change: LinkedInSLAChange = LinkedInSLAChange.query.filter_by(
            client_sdr_id=sdr.id
        ).order_by(LinkedInSLAChange.created_at.desc()).first()

        # If there are no status change records, we create one from 0 to whatever the current SLA is
        if not most_recent_sla_change:
            new_sla_change = LinkedInSLAChange(
                client_sdr_id=sdr.id,
                old_sla_value=0,
                new_sla_value=sdr.weekly_li_outbound_target,
            )
            db.session.add(new_sla_change)
            db.session.commit()
            most_recent_sla_change = new_sla_change

        # If the most recent warmup status change record is within 7 days, then do nothing
        if most_recent_sla_change and (datetime.utcnow() - most_recent_sla_change.created_at).days < 7:
            continue

        # Get the SLA warmup schedule
        warmup_schedule: WarmupScheduleLinkedIn = WarmupScheduleLinkedIn.query.filter_by(
            client_sdr_id=sdr.id
        ).first()

        # If there is no warmup schedule, we create one with the conservative schedule
        if not warmup_schedule:
            create_warmup_schedule_linkedin(sdr.id)

        # Get the next SLA
        next_sla = warmup_schedule.get_next_sla(sdr.weekly_li_outbound_target)

        # Update the SLA
        update_sdr_linkedin_sla(
            client_sdr_id=sdr.id,
            new_sla_value=next_sla
        )

        # Send a slack notification
        send_slack_message(
            message="SLA for {} has been updated from {} (#{}) to {}.".format(sdr.name, sdr.id, old_sla, next_sla),
            webhook_urls=[URL_MAP["operations-sla-updater"]]
        )

    send_slack_message(
        message="LinkedIn SLA update task complete.",
        webhook_urls=[URL_MAP["operations-sla-updater"]]
    )
    return True


def update_sdr_linkedin_sla(
    client_sdr_id: int,
    new_sla_value: int,
) -> tuple[bool, int]:
    """Updates the LinkedIn SLA for a Client SDR

    Args:
        client_sdr_id (int): _description_
        new_sla_value (int): _description_

    Returns:
        tuple[bool, int]: A boolean indicating whether the update was successful and the
        ID of the new status change record
    """
    from src.client.services import update_phantom_buster_launch_schedule

    # Get the SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False, None

    # Create the new status change record
    new_status_change = LinkedInSLAChange(
        client_sdr_id=client_sdr_id,
        old_sla_value=sdr.weekly_li_outbound_target,
        new_sla_value=new_sla_value
    )
    db.session.add(new_status_change)
    db.session.commit()

    # Update the SDR
    sdr.weekly_li_outbound_target = new_sla_value
    db.session.commit()

    # Update the warmup status
    sdr.update_warmup_status()

    # Update the Phantom Buster launch schedule
    update_phantom_buster_launch_schedule(client_sdr_id)

    return True, new_status_change.id


def get_linkedin_sla_records(client_sdr_id: int) -> list[LinkedInSLAChange]:
    """Gets the LinkedIn SLA change records for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        list[LinkedInSLAChange]: The LinkedIn warmup status change records for the Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    status_changes: list[LinkedInSLAChange] = LinkedInSLAChange.query.filter_by(
        client_sdr_id=client_sdr_id
    ).all()

    return status_changes
