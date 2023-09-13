from datetime import datetime, timedelta
from typing import Optional
from app import db, celery
from sqlalchemy import or_

from src.client.models import Client, ClientSDR, LinkedInSLAChange, WarmupScheduleLinkedIn, SLASchedule
from src.utils.datetime.dateutils import get_current_monday_friday
from src.utils.slack import send_slack_message, URL_MAP
from src.voyager.linkedin import LinkedIn


LINKEDIN_WARUMP_CONSERVATIVE = [5, 25, 50, 75, 90]
LINKEDIN_WARM_THRESHOLD = 90

EMAIL_WARMUP_CONSERVATIVE = [10, 25, 50, 100, 150]
EMAIL_WARM_THRESHOLD = 150


def compute_sdr_linkedin_health(
    client_sdr_id: int,
) -> tuple[bool, float, dict]:
    """Computes the LinkedIn health for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        tuple[bool, float, dict]: A boolean indicating whether the computation was successful, the LinkedIn health, and the LinkedIn health details
    """
    bad_title_words = ['sales', 'sale', 'sdr', 'bdr', 'account executive', 'account exec', 'business development', 'sales development']

    # Get the SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get the Voyager client
    voyager: LinkedIn = LinkedIn(sdr.id)
    is_valid = voyager.is_valid()
    if not is_valid:
        return False, None, None

    # Get the user profile
    profile = voyager.get_user_profile()

    # Get "mini_profile" details
    mini_profile = profile.get("mini_profile", None)
    if mini_profile:
        # Title
        title = mini_profile.get("occupation")
        sdr.title = title
        for word in bad_title_words:
            if word in title.lower():
                title_fail_reason = "Your title contains the word '{}'. Avoid sales-y words in your title.".format(word)
                sdr.li_health_good_title = False
                break

        # Cover photo
        background_image = mini_profile.get("backgroundImage")
        background_image = background_image.get(
            "com.linkedin.common.VectorImage") if background_image else None
        if background_image:
            root_url = background_image.get("rootUrl")
            artifacts = background_image.get("artifacts")
            last_artifact = artifacts[-1] if artifacts else None
            background_image_url = root_url + \
                last_artifact.get(
                    "fileIdentifyingUrlPathSegment") if last_artifact else None
            sdr.li_cover_img_url = background_image_url
            sdr.li_health_cover_image = True

        # Profile picture
        profile_picture = mini_profile.get("picture")
        profile_picture = profile_picture.get(
            "com.linkedin.common.VectorImage") if profile_picture else None
        if profile_picture:
            root_url = profile_picture.get("rootUrl")
            artifacts = profile_picture.get("artifacts")
            last_artifact = artifacts[-1] if artifacts else None
            profile_picture_url = root_url + \
                last_artifact.get(
                    "fileIdentifyingUrlPathSegment") if last_artifact else None
            profile_picture_expire = last_artifact.get(
                "expiresAt") if last_artifact else None
            sdr.img_url = profile_picture_url
            sdr.img_expire = profile_picture_expire
            sdr.li_health_profile_picture = True

    # Get premium subscriber details
    premium_subscriber = profile.get("premiumSubscriber", None)
    sdr.li_health_premium = premium_subscriber if premium_subscriber else False

    # Calulate the LinkedIn health
    HEALTH_MAX = 40
    li_health = 0
    if sdr.li_health_good_title:
        li_health += 10
    if sdr.li_health_cover_image:
        li_health += 10
    if sdr.li_health_profile_photo:
        li_health += 10
    if sdr.li_health_premium:
        li_health += 10

    # Update the SDR
    sdr.li_health = li_health / HEALTH_MAX
    db.session.commit()

    details = {
        "title": {
            "status": sdr.li_health_good_title,
            "message": "Good LinkedIn title" if sdr.li_health_good_title else (title_fail_reason if title_fail_reason else "Your title may appear sales-y. Avoid sales-y words in your title.")
        },
        "li_health_premium": {
            "status": sdr.li_health_premium,
            "message": "Premium LinkedIn account" if sdr.li_health_premium else "You do not have a premium LinkedIn account. Consider upgrading to a premium account.",
        },
        "img_url": {
            "status": sdr.li_health_profile_photo,
            "message": "Profile picture found" if sdr.li_health_profile_photo else "You do not have a profile picture. Consider adding one.",
        },
        "li_cover_img_url": {
            "status": sdr.li_health_cover_image,
            "message": "Cover photo found" if sdr.li_health_cover_image else "You do not have a cover photo. Consider adding one.",
        }
    }

    return True, li_health, details


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


def get_sla_schedules_for_sdr(
    client_sdr_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> list[dict]:
    """Gets all the SLA schedules for a Client SDR. If timeframes are specified, then returns the SLA schedules in the timeframe.

    Args:
        client_sdr_id (int): The id of the Client SDR
        start_date (Optional[datetime], optional): The start date of the timeframe. Defaults to None.
        end_date (Optional[datetime], optional): The end date of the timeframe. Defaults to None.

    Returns:
        list[dict]: The SLA schedules for the Client SDR
    """
    # Get all SLA schedules for the Client SDR
    schedule: SLASchedule = SLASchedule.query.filter_by(
        client_sdr_id=client_sdr_id
    )

    # If timeframes are specified, then filter by the timeframes
    if start_date:
        schedule = schedule.filter(SLASchedule.start_date >= start_date)
    if end_date:
        schedule = schedule.filter(SLASchedule.end_date <= end_date)

    # Order by most recent first
    schedule = schedule.order_by(
        SLASchedule.created_at.desc()
    ).all()

    # Convert to dicts
    schedule_dicts = []
    for entry in schedule:
        schedule_dicts.append(entry.to_dict())

    return schedule_dicts


def create_sla_schedule(
    client_sdr_id: int,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    linkedin_volume: Optional[int] = 5,
    linkedin_special_notes: Optional[str] = None,
    email_volume: Optional[int] = 5,
    email_special_notes: Optional[str] = None,
) -> int:
    """Creates an SLA schedule for a Client SDR.

    The start dates will automatically adjust to be the Monday of the specified week, and the Friday of the same week.

    Args:
        client_sdr_id (int): The id of the Client SDR
        start_date (datetime): The start date of the timeframe
        end_date (datetime): The end date of the timeframe
        linkedin_volume (Optional[int], optional): Volume of LinkedIn outbound during this range. Defaults to 5.
        linkedin_special_notes (Optional[str], optional): Special notes regarding the reason for the volume. Defaults to None.
        email_volume (Optional[int], optional): Volume of email outbound during this range. Defaults to 5.
        email_special_notes (Optional[str], optional): Special notes regarding the reason for the volume. Defaults to None.

    Returns:
        int: The id of the SLA schedule
    """
    # Get the monday of the start date's given week
    start_date, end_date = get_current_monday_friday(start_date)

    # Calculate the week number
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    week = (start_date - sdr.created_at.date()).days // 7
    if week < 0:
        week = 0

    # Create the SLA schedule
    sla_schedule: SLASchedule = SLASchedule(
        client_sdr_id=client_sdr_id,
        start_date=start_date,
        end_date=end_date,
        linkedin_volume=linkedin_volume,
        linkedin_special_notes=linkedin_special_notes,
        email_volume=email_volume,
        email_special_notes=email_special_notes,
        week=week
    )
    db.session.add(sla_schedule)
    db.session.commit()

    return sla_schedule.id


@celery.task(bind=True, max_retries=3)
def automatic_sla_schedule_loader(self):
    """Loads SLA schedules for all active SDRs, if applicable. This task is run every Monday at 9AM PST."""

    # Get the IDs of all active Clients
    active_client_ids: list[int] = [
        client.id for client in Client.query.filter_by(active=True).all()]

    # Get all active SDRs
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True,
        ClientSDR.client_id.in_(active_client_ids)
    ).all()

    # Update the SLA for each SDR
    for sdr in sdrs:
        load_sla_schedules(sdr.id)

    send_slack_message(
        message="All Active SDRs have had their SLA schedules (attempted to) updated.",
        webhook_urls=[URL_MAP["operations-sla-updater"]]
    )
    return True


def load_sla_schedules(
    client_sdr_id: int
) -> tuple[bool, list[int]]:
    """'Loads' SLA schedules. This function will check for 3 weeks worth of SLA schedules into the future for a given
    SDR, and if there are not 3 weeks worth of SLA schedules, it will create them.

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        tuple[bool, list[int]]: A boolean indicating whether the load was successful and a list of the SLA schedule ids
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get the furthest into the future SLA schedule
    furthest_sla_schedule: SLASchedule = SLASchedule.query.filter_by(
        client_sdr_id=client_sdr_id
    ).order_by(
        SLASchedule.start_date.desc()
    ).first()

    # If there are no SLA schedules, then we create 3 weeks worth of SLA schedules
    if not furthest_sla_schedule:
        week_0_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow(),
            linkedin_volume=LINKEDIN_WARUMP_CONSERVATIVE[0]
        )
        week_1_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow() + timedelta(days=7),
            linkedin_volume=LINKEDIN_WARUMP_CONSERVATIVE[1]
        )
        week_2_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow() + timedelta(days=14),
            linkedin_volume=LINKEDIN_WARUMP_CONSERVATIVE[2]
        )

        load_sla_alert(client_sdr_id, [week_0_id, week_1_id, week_2_id])
        return True, [week_0_id, week_1_id, week_2_id]

    # Determine how many schedules we should have
    # We determine by taking today's date, finding the Monday of this week, and calculating 2 weeks from that Monday
    monday, _ = get_current_monday_friday(datetime.utcnow())
    two_weeks_from_monday = monday + timedelta(days=14)
    weeks_needed = (two_weeks_from_monday -
                    furthest_sla_schedule.start_date.date()).days // 7

    # If there are less than 3 weeks between the furthest SLA schedule and today, then we create the missing SLA schedules
    if weeks_needed > 0:
        new_schedule_ids = []

        # TODO: Add Email volume in the future
        li_volume = furthest_sla_schedule.linkedin_volume
        email_volume = furthest_sla_schedule.email_volume
        for i in range(weeks_needed):
            # LINKEDIN: If our volume is in the range of the conservative schedule, then we should bump the volume. Otherwise, we keep the volume
            if li_volume > LINKEDIN_WARUMP_CONSERVATIVE[0] and li_volume < LINKEDIN_WARUMP_CONSERVATIVE[-1]:
                for schedule_li_volume in enumerate(LINKEDIN_WARUMP_CONSERVATIVE):
                    if schedule_li_volume > li_volume:
                        li_volume = schedule_li_volume
                        break

            # EMAIL: If our volume is in the range of the conservative schedule, then we should bump the volume. Otherwise, we keep the volume
            if email_volume > EMAIL_WARMUP_CONSERVATIVE[0] and email_volume < EMAIL_WARMUP_CONSERVATIVE[-1]:
                for schedule_email_volume in enumerate(EMAIL_WARMUP_CONSERVATIVE):
                    if schedule_email_volume > email_volume:
                        email_volume = schedule_email_volume
                        break

            schedule_id = create_sla_schedule(
                client_sdr_id=client_sdr_id,
                start_date=datetime.utcnow() + timedelta(days=7 * (i+1)),
                linkedin_volume=li_volume,
                email_volume=email_volume
            )
            new_schedule_ids.append(schedule_id)

        load_sla_alert(client_sdr_id, new_schedule_ids)
        return True, new_schedule_ids

    send_slack_message(
        message="No SLA schedules created for {}. Schedules are up to date.".format(
            client_sdr.name),
        webhook_urls=[URL_MAP["operations-sla-updater"]]
    )
    return True, []


def load_sla_alert(
    client_sdr_id: int,
    new_schedule_ids: list[int]
) -> bool:
    """Helps `load_sla_schedules` by sending a slack alert

    Args:
        client_sdr_id (int): The id of the Client SDR
        new_schedule_ids (list[int]): The ids of the new SLA schedules

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the client SDR
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get the schedules
    schedules: list[SLASchedule] = SLASchedule.query.filter(
        SLASchedule.id.in_(new_schedule_ids)
    ).all()

    # Construct the slack message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "SLA schedules automatically created for *{}*.".format(client_sdr.name)
            }
        }
    ]

    # Add the schedules to the slack message
    for schedule in schedules:
        week_num = (schedule.start_date.date() -
                    client_sdr.created_at.date()).days // 7
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*{}* - *{}* (Week {}): {} LinkedIn | {} Email".format(
                        schedule.start_date.date().strftime("%B %d, %Y"),
                        schedule.end_date.date().strftime("%B %d, %Y"),
                        week_num,
                        schedule.linkedin_volume,
                        schedule.email_volume
                    )
                }
            }
        )

    send_slack_message(
        message="SLA schedules created for {}.".format(client_sdr_id),
        webhook_urls=[URL_MAP["operations-sla-updater"]],
        blocks=blocks
    )

    return True


def update_sla_schedule(
    client_sdr_id: int,
    sla_schedule_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    linkedin_volume: Optional[int] = None,
    linkedin_special_notes: Optional[str] = None,
    email_volume: Optional[int] = None,
    email_special_notes: Optional[str] = None,
) -> tuple[bool, str]:
    """Updates an SLA schedule for a Client SDR. Note that time frames cannot be updated.

    If no SLA schedule id is specified, then the start date must be specified.

    Args:
        client_sdr_id (int): The id of the Client SDR
        sla_schedule_id (int): The id of the SLA schedule
        start_date (Optional[datetime], optional): The start date of the timeframe. Defaults to None.
        linkedin_volume (Optional[int], optional): Volume of LinkedIn outbound during this range. Defaults to None.
        linkedin_special_notes (Optional[str], optional): Special notes regarding the reason for the volume. Defaults to None.
        email_volume (Optional[int], optional): Volume of email outbound during this range. Defaults to None.
        email_special_notes (Optional[str], optional): Special notes regarding the reason for the volume. Defaults to None.

    Returns:
        tuple[bool, str]: A boolean indicating whether the update was successful and a message
    """
    # Get the SLA schedule, if applicable
    if sla_schedule_id:
        sla_schedule: SLASchedule = SLASchedule.query.get(sla_schedule_id)
    else:
        if not start_date:
            return False, "If no SLA schedule id is specified, then the start date must be specified."
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr_id,
            SLASchedule.start_date <= start_date,
            SLASchedule.end_date >= start_date,
        ).first()

    if not sla_schedule:
        return False, "No SLA schedule found."

    # Update the SLA schedule
    if linkedin_volume:
        sla_schedule.linkedin_volume = linkedin_volume
    if linkedin_special_notes:
        sla_schedule.linkedin_special_notes = linkedin_special_notes
    if email_volume:
        sla_schedule.email_volume = email_volume
    if email_special_notes:
        sla_schedule.email_special_notes = email_special_notes

    db.session.commit()

    return True, "Success"


def deactivate_sla_schedules(
    client_sdr_id: int,
) -> bool:
    """Deactives all SLA schedules (current week and future weeks) for an SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the SLA schedules that start after this Monday
    monday, _ = get_current_monday_friday(datetime.utcnow())
    sla_schedules: list[SLASchedule] = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id,
        SLASchedule.start_date >= monday
    ).all()

    # Deactivate the SLA schedules
    now = datetime.utcnow()
    for schedule in sla_schedules:
        schedule.linkedin_volume = 0
        schedule.email_volume = 0
        schedule.linkedin_special_notes = "SDR Deactivated on {}".format(now)
        schedule.email_special_notes = "SDR Deactivated on {}".format(now)

    db.session.commit()

    return True


# DEPRECATED
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

# DEPRECATED


@celery.task(bind=True, max_retries=3)
def auto_update_sdr_linkedin_sla_task(self):
    """Updates the LinkedIn SLA for all active SDRs, if applicable. This task is run every 24 hours."""
    # Get the IDs of all active Clients
    active_client_ids: list[int] = [
        client.id for client in Client.query.filter_by(active=True).all()]

    # Get all active SDRs that do not have warmup LinkedIn complete
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True,
        or_(
            ClientSDR.warmup_linkedin_complete == False,
            ClientSDR.warmup_linkedin_complete == None
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
            message="SLA for {} has been updated from {} (#{}) to {}.".format(
                sdr.name, sdr.id, old_sla, next_sla),
            webhook_urls=[URL_MAP["operations-sla-updater"]]
        )

    send_slack_message(
        message="LinkedIn SLA update task complete.",
        webhook_urls=[URL_MAP["operations-sla-updater"]]
    )
    return True


# DEPRECATED
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


# DEPRECATED
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
