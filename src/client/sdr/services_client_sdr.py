from datetime import datetime, timedelta
from typing import Optional, TypedDict, Literal
from app import db, celery
from sqlalchemy import or_
from src.campaigns.models import OutboundCampaign

from src.client.models import (
    Client,
    ClientArchetype,
    ClientAssetArchetypeReasonMapping,
    ClientAssets,
    ClientSDR,
    SLASchedule,
)
from src.message_generation.models import GeneratedMessage
from src.utils.datetime.dateutils import (
    get_current_monday_friday,
    get_current_monday_sunday,
)
from src.utils.slack import send_slack_message, URL_MAP
from src.voyager.linkedin import LinkedIn


LINKEDIN_WARUMP_CONSERVATIVE = [5, 25, 50, 75, 90]
LINKEDIN_WARM_THRESHOLD = 90

EMAIL_WARMUP_CONSERVATIVE = [10, 25, 50, 100, 150]
EMAIL_WARM_THRESHOLD = 150


def update_sdr_default_transformer_blacklist(
    client_sdr_id: int, blocklist: list[str]
) -> bool:
    """Updates the default transformer blacklist for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR
        blocklist (list[str]): The default transformer blacklist

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the Client SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    # Update the Client SDR
    sdr.default_transformer_blocklist = blocklist
    db.session.commit()

    return True


def compute_sdr_linkedin_health(
    client_sdr_id: int,
) -> tuple[bool, float, dict]:
    """Computes the LinkedIn health for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        tuple[bool, float, dict]: A boolean indicating whether the computation was successful, the LinkedIn health, and the LinkedIn health details
    """
    bad_title_words = [
        "sdr",
        "bdr",
        "account executive",
        "sales executive" "account exec",
        "business development",
        "sales development",
    ]

    # Get the SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get the Voyager client
    voyager: LinkedIn = LinkedIn(sdr.id)
    is_valid = voyager.is_valid()
    if not is_valid:
        return False, None, None

    # Get the user profile
    profile = voyager.get_user_profile()
    if not profile:
        return False, None, None

    # Get "mini_profile" details
    mini_profile = profile.get("miniProfile", None)
    title_fail_reason = ""
    if mini_profile:
        # Title
        title = mini_profile.get("occupation")
        sdr.title = title
        sdr.li_health_good_title = True
        for word in bad_title_words:
            if word in title.lower():
                title_fail_reason = "Your title contains the word '{}'. Avoid sales-y words in your title.".format(
                    word
                )
                sdr.li_health_good_title = False
                break

        # Cover photo
        background_image = mini_profile.get("backgroundImage")
        background_image = (
            background_image.get("com.linkedin.common.VectorImage")
            if background_image
            else None
        )
        if background_image:
            root_url = background_image.get("rootUrl")
            artifacts = background_image.get("artifacts")
            last_artifact = artifacts[-1] if artifacts else None
            background_image_url = (
                root_url + last_artifact.get("fileIdentifyingUrlPathSegment")
                if last_artifact
                else None
            )
            sdr.li_cover_img_url = background_image_url
            sdr.li_health_cover_image = True

        # Profile picture
        profile_picture = mini_profile.get("picture")
        profile_picture = (
            profile_picture.get("com.linkedin.common.VectorImage")
            if profile_picture
            else None
        )
        if profile_picture:
            root_url = profile_picture.get("rootUrl")
            artifacts = profile_picture.get("artifacts")
            last_artifact = artifacts[-1] if artifacts else None
            profile_picture_url = (
                root_url + last_artifact.get("fileIdentifyingUrlPathSegment")
                if last_artifact
                else None
            )
            profile_picture_expire = (
                last_artifact.get("expiresAt") if last_artifact else None
            )
            sdr.img_url = profile_picture_url
            sdr.img_expire = profile_picture_expire
            sdr.li_health_profile_photo = True

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
    sdr.li_health = (li_health / HEALTH_MAX) * 100
    db.session.commit()

    details = [
        {
            "criteria": "Good Title",
            "status": sdr.li_health_good_title,
            "message": (
                "Good LinkedIn title"
                if sdr.li_health_good_title
                else (
                    title_fail_reason
                    if title_fail_reason
                    else "Your title may appear sales-y. Avoid sales-y words in your title."
                )
            ),
        },
        {
            "criteria": "Premium Account",
            "status": sdr.li_health_premium,
            "message": (
                "Premium LinkedIn account"
                if sdr.li_health_premium
                else "You do not have a premium LinkedIn account. Consider upgrading to a premium account."
            ),
        },
        {
            "criteria": "Profile Picture",
            "status": sdr.li_health_profile_photo,
            "message": (
                "Profile picture found"
                if sdr.li_health_profile_photo
                else "You do not have a profile picture. Consider adding one."
            ),
        },
        {
            "criteria": "Cover Photo",
            "status": sdr.li_health_cover_image,
            "message": (
                "Cover photo found"
                if sdr.li_health_cover_image
                else "You do not have a cover photo. Consider adding one."
            ),
        },
    ]

    return True, sdr.li_health, details


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


def update_sdr_sla_targets(
    client_sdr_id: int,
    weekly_linkedin_target: Optional[int] = None,
    weekly_email_target: Optional[int] = None,
) -> tuple[bool, str]:
    """Updates the SLA targets for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR
        weekly_linkedin_target (int): The weekly LinkedIn target
        weekly_email_target (int): The weekly email target

    Returns:
        tuple[bool, str]: A boolean indicating whether the update was successful and a message
    """
    if not weekly_linkedin_target and not weekly_email_target:
        return False, "No targets specified."

    # Get the Client SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False, "Client SDR not found."

    if not weekly_linkedin_target:
        weekly_linkedin_target = sdr.weekly_li_outbound_target
    if not weekly_email_target:
        weekly_email_target = sdr.weekly_email_outbound_target

    old_weekly_linkedin_target = sdr.weekly_li_outbound_target
    old_weekly_email_target = sdr.weekly_email_outbound_target

    # Update the Client SDR
    sdr.weekly_li_outbound_target = weekly_linkedin_target
    sdr.weekly_email_outbound_target = weekly_email_target
    db.session.commit()

    # Check if the current week's SLA schedule hits warmup, and adjust warmup status accordingly
    monday, _ = get_current_monday_friday(datetime.utcnow())
    sla_schedule: SLASchedule = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id,
        SLASchedule.start_date <= monday,
        SLASchedule.end_date >= monday,
    ).first()
    if sla_schedule:
        if sla_schedule.linkedin_volume >= LINKEDIN_WARM_THRESHOLD:
            sdr.warmup_linkedin_complete = True
        # TODO: Bring in an email warmup complete check
        # if sla_schedule.email_volume >= EMAIL_WARM_THRESHOLD:
        #     sdr.warmup_status_email = True
        db.session.commit()

    # Adjust future week's SLA schedules, if they are at MAX then bump it up to the new target
    sla_schedules: list[SLASchedule] = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id, SLASchedule.start_date > monday
    ).all()
    for schedule in sla_schedules:
        if schedule.linkedin_volume == old_weekly_linkedin_target:
            schedule.linkedin_volume = weekly_linkedin_target
        if schedule.email_volume == old_weekly_email_target:
            schedule.email_volume = weekly_email_target
    db.session.commit()

    return True, "Success"


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
    schedule: SLASchedule = SLASchedule.query.filter_by(client_sdr_id=client_sdr_id)

    # If timeframes are specified, then filter by the timeframes
    if start_date:
        schedule = schedule.filter(SLASchedule.start_date >= start_date)
    if end_date:
        schedule = schedule.filter(SLASchedule.end_date <= end_date)

    # Order by most recent first
    schedule = schedule.order_by(SLASchedule.created_at.desc()).all()

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

    The start dates will automatically adjust to be the Monday of the specified week, and the Sunday of the same week.

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
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get the monday of the start date's given week
    start_date, end_date = get_current_monday_sunday(start_date)

    # Get the monday of the SDR creation week
    sdr_monday, _ = get_current_monday_sunday(sdr.created_at)

    # Calculate the week number
    week = (start_date - sdr_monday).days // 7
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
        week=week,
    )
    db.session.add(sla_schedule)
    db.session.commit()

    return sla_schedule.id


@celery.task(bind=True, max_retries=3)
def automatic_sla_schedule_loader(self):
    """Loads SLA schedules for all active SDRs, if applicable. This task is run every Monday at 9AM PST."""

    # Get the IDs of all active Clients
    active_client_ids: list[int] = [
        client.id for client in Client.query.filter_by(active=True).all()
    ]

    # Get all active SDRs
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True, ClientSDR.client_id.in_(active_client_ids)
    ).all()

    # Update the SLA for each SDR
    for sdr in sdrs:
        load_sla_schedules(sdr.id)

    send_slack_message(
        message="All Active SDRs have had their SLA schedules (attempted to) updated.",
        webhook_urls=[URL_MAP["operations-sla-updater"]],
    )
    return True


def load_sla_schedules(client_sdr_id: int) -> tuple[bool, list[int]]:
    """'Loads' SLA schedules. This function will check for 3 weeks worth of SLA schedules into the future for a given
    SDR, and if there are not 5 weeks worth of SLA schedules, it will create them.

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        tuple[bool, list[int]]: A boolean indicating whether the load was successful and a list of the SLA schedule ids
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    adjust_sla_schedules(client_sdr_id)

    # Get the furthest into the future SLA schedule
    furthest_sla_schedule: SLASchedule = (
        SLASchedule.query.filter_by(client_sdr_id=client_sdr_id)
        .order_by(SLASchedule.start_date.desc())
        .first()
    )

    # If there are no SLA schedules, then we create 3 weeks worth of SLA schedules
    if not furthest_sla_schedule:
        week_0_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow(),
            linkedin_volume=min(
                LINKEDIN_WARUMP_CONSERVATIVE[1],
                client_sdr.weekly_li_outbound_target or LINKEDIN_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
            email_volume=min(
                EMAIL_WARMUP_CONSERVATIVE[1],
                client_sdr.weekly_email_outbound_target or EMAIL_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
        )
        week_1_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow() + timedelta(days=7),
            linkedin_volume=min(
                LINKEDIN_WARUMP_CONSERVATIVE[2],
                client_sdr.weekly_li_outbound_target or LINKEDIN_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
            email_volume=min(
                EMAIL_WARMUP_CONSERVATIVE[2],
                client_sdr.weekly_email_outbound_target or EMAIL_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
        )
        week_2_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow() + timedelta(days=14),
            linkedin_volume=min(
                LINKEDIN_WARUMP_CONSERVATIVE[3],
                client_sdr.weekly_li_outbound_target or LINKEDIN_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
            email_volume=min(
                EMAIL_WARMUP_CONSERVATIVE[3],
                client_sdr.weekly_email_outbound_target or EMAIL_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
        )
        week_3_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow() + timedelta(days=21),
            linkedin_volume=min(
                LINKEDIN_WARUMP_CONSERVATIVE[4],
                client_sdr.weekly_li_outbound_target or LINKEDIN_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
            email_volume=min(
                EMAIL_WARMUP_CONSERVATIVE[4],
                client_sdr.weekly_email_outbound_target or EMAIL_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
        )
        week_4_id = create_sla_schedule(
            client_sdr_id=client_sdr_id,
            start_date=datetime.utcnow() + timedelta(days=28),
            linkedin_volume=min(
                LINKEDIN_WARUMP_CONSERVATIVE[4],
                client_sdr.weekly_li_outbound_target or LINKEDIN_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
            email_volume=min(
                EMAIL_WARMUP_CONSERVATIVE[4],
                client_sdr.weekly_email_outbound_target or EMAIL_WARM_THRESHOLD,
            ),  # Take the minimum in case the target is less than the conservative schedule
        )

        load_sla_alert(
            client_sdr_id, [week_0_id, week_1_id, week_2_id, week_3_id, week_4_id]
        )
        return True, [week_0_id, week_1_id, week_2_id, week_3_id, week_4_id]

    # Determine how many schedules we should have
    # We determine by taking today's date, finding the Monday of this week, and calculating 4 weeks from that Monday
    monday, _ = get_current_monday_friday(datetime.utcnow())
    four_weeks_from_monday = monday + timedelta(days=28)
    weeks_needed = (
        four_weeks_from_monday - furthest_sla_schedule.start_date.date()
    ).days // 7

    # If there are less than 5 weeks between the furthest SLA schedule and today, then we create the missing SLA schedules
    if weeks_needed > 0:
        new_schedule_ids = []

        li_volume = furthest_sla_schedule.linkedin_volume
        email_volume = furthest_sla_schedule.email_volume

        for i in range(weeks_needed):
            # LINKEDIN: If our volume is in the range of the conservative schedule, then we should bump the volume. Otherwise, we bump to the weekly target
            if (
                li_volume > LINKEDIN_WARUMP_CONSERVATIVE[0]
                and li_volume < LINKEDIN_WARUMP_CONSERVATIVE[-1]
            ):
                for schedule_li_volume in LINKEDIN_WARUMP_CONSERVATIVE:
                    if schedule_li_volume > li_volume:
                        li_volume = min(
                            schedule_li_volume, client_sdr.weekly_li_outbound_target
                        )  # Take the minimum in case the target is less than the conservative schedule
                        break

            # LINKEDIN: If we are at the end of the conservative schedule, then we should bump to the weekly target
            if li_volume >= LINKEDIN_WARUMP_CONSERVATIVE[-1]:
                li_volume = client_sdr.weekly_li_outbound_target

            # EMAIL: If our volume is in the range of the conservative schedule, then we should bump the volume. Otherwise, we bump to the weekly target
            if (
                email_volume > EMAIL_WARMUP_CONSERVATIVE[0]
                and email_volume < EMAIL_WARMUP_CONSERVATIVE[-1]
            ):
                for schedule_email_volume in EMAIL_WARMUP_CONSERVATIVE:
                    if schedule_email_volume > email_volume:
                        email_volume = min(
                            schedule_email_volume,
                            client_sdr.weekly_email_outbound_target,
                        )  # Take the minimum in case the target is less than the conservative schedule
                        break

            # EMAIL: If we are at the end of the conservative schedule, then we should bump to the weekly target
            if email_volume >= EMAIL_WARMUP_CONSERVATIVE[-1]:
                email_volume = client_sdr.weekly_email_outbound_target

            schedule_id = create_sla_schedule(
                client_sdr_id=client_sdr_id,
                start_date=furthest_sla_schedule.start_date
                + timedelta(days=7 * (i + 1)),
                linkedin_volume=li_volume,
                email_volume=email_volume,
            )
            new_schedule_ids.append(schedule_id)

        load_sla_alert(client_sdr_id, new_schedule_ids)
        return True, new_schedule_ids

    send_slack_message(
        message="No SLA schedules created for {}. Schedules are up to date.".format(
            client_sdr.name
        ),
        webhook_urls=[URL_MAP["operations-sla-updater"]],
    )
    return True, []


def adjust_sla_schedules(client_sdr_id: int) -> bool:
    """Adjusts the SLA schedules for a Client SDR. This function will look at the all_time send count to ensure that messages have bee nsent, and if not, it will adjust the SLA schedules accordingly.

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        bool: True if successful, False otherwise
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get the all time send count
    stats = get_sdr_send_statistics(client_sdr_id=client_sdr_id)
    all_time_send_count = stats.get("all_time_send_count", 0)

    # Get all future SLA schedules
    monday, _ = get_current_monday_friday(datetime.utcnow())
    sla_schedules: list[SLASchedule] = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id, SLASchedule.start_date >= monday
    ).all()

    # Adjust the SLA schedules to be equal to last weeks
    last_week_sla_schedule: SLASchedule = (
        SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr_id,
            SLASchedule.start_date < monday,
        )
        .order_by(SLASchedule.start_date.desc())
        .first()
    )

    # If the all time send count is 0, then we adjust the SLA schedules
    if all_time_send_count != 0:
        # If it is not, let us make sure the "readjust" any ai_adjusted schedules
        for schedule in sla_schedules:
            if schedule.linkedin_ai_adjusted:
                schedule.linkedin_ai_adjusted = False
                schedule.linkedin_volume = last_week_sla_schedule.linkedin_volume
            if schedule.email_ai_adjusted:
                schedule.email_ai_adjusted = False
                schedule.email_volume = last_week_sla_schedule.email_volume
        db.session.commit()

        return False  # No need to adjust the SLA schedules

    db.session.commit()

    return True


def load_sla_alert(client_sdr_id: int, new_schedule_ids: list[int]) -> bool:
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
                "text": "SLA schedules automatically created for *{}*.".format(
                    client_sdr.name
                ),
            },
        }
    ]

    # Add the schedules to the slack message
    for schedule in schedules:
        week_num = (schedule.start_date.date() - client_sdr.created_at.date()).days // 7
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
                        schedule.email_volume,
                    ),
                },
            }
        )

    send_slack_message(
        message="SLA schedules created for {}.".format(client_sdr_id),
        webhook_urls=[URL_MAP["operations-sla-updater"]],
        blocks=blocks,
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
            return (
                False,
                "If no SLA schedule id is specified, then the start date must be specified.",
            )
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr_id,
            SLASchedule.start_date <= start_date,
            SLASchedule.end_date >= start_date,
        ).first()

        if not sla_schedule:
            sla_schedule: SLASchedule = (
                SLASchedule.query.filter(
                    SLASchedule.client_sdr_id == client_sdr_id,
                    SLASchedule.start_date <= start_date,
                )
                .order_by(SLASchedule.start_date.desc())
                .first()
            )

    # Make sure that the schedule is not for a past week (current week OK)
    monday, _ = get_current_monday_friday(datetime.utcnow())
    if sla_schedule.start_date.date() < monday:
        return False, "Cannot update an SLA schedule for a past week."

    if not sla_schedule:
        return False, "No SLA schedule found."

    # Update the SLA schedule
    if linkedin_volume:
        sla_schedule.linkedin_volume = linkedin_volume
    if email_volume:
        sla_schedule.email_volume = email_volume
    sla_schedule.linkedin_special_notes = linkedin_special_notes
    sla_schedule.email_special_notes = email_special_notes

    db.session.commit()

    return True, "Success"


def update_sla_schedule_email_limit(client_sdr_id: int, daily_limit: int) -> bool:
    """Updates the daily email limit for an SDR

    Args:
        client_sdr_id (int): The id of the Client SDR
        daily_limit (int): The daily email limit

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the SLA schedules that starts on this Monday
    monday, _ = get_current_monday_friday(datetime.utcnow())
    sla_schedule: list[SLASchedule] = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id, SLASchedule.start_date >= monday
    ).all()

    weekly_limit = daily_limit * 5

    # Update the SLA schedule
    for schedule in sla_schedule:
        schedule.email_volume = weekly_limit

    db.session.commit()

    return True


def deactivate_sla_schedules(
    client_sdr_id: int,
) -> bool:
    """Deactives all SLA schedules (current week and future weeks) for an SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the SLA schedules that starts on this Monday
    monday, _ = get_current_monday_friday(datetime.utcnow())
    sla_schedule: SLASchedule = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id, SLASchedule.start_date == monday
    ).first()

    # Make note that the SDR was deactivated
    now = datetime.utcnow()
    sla_schedule.linkedin_special_notes = "SDR Deactivated on {}".format(now)
    sla_schedule.email_special_notes = "SDR Deactivated on {}".format(now)
    db.session.commit()

    return True


def update_custom_conversion_pct(
    client_sdr_id: int,
    conversion_sent_pct: Optional[float] = None,
    conversion_open_pct: Optional[float] = None,
    conversion_reply_pct: Optional[float] = None,
    conversion_demo_pct: Optional[float] = None,
) -> tuple[bool, str]:
    """Updates the custom conversion percentages for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR
        conversion_sent_pct (Optional[float], optional): The custom conversion percentage for sent. Defaults to None.
        conversion_open_pct (Optional[float], optional): The custom conversion percentage for open. Defaults to None.
        conversion_reply_pct (Optional[float], optional): The custom conversion percentage for reply. Defaults to None.
        conversion_demo_pct (Optional[float], optional): The custom conversion percentage for demo. Defaults to None.

    Returns:
        tuple[bool, str]: A boolean indicating whether the update was successful and a message
    """
    # Get the Client SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False, "Client SDR not found."

    # Update the Client SDR
    if conversion_sent_pct:
        sdr.conversion_sent_pct = conversion_sent_pct
    if conversion_open_pct:
        sdr.conversion_open_pct = conversion_open_pct
    if conversion_reply_pct:
        sdr.conversion_reply_pct = conversion_reply_pct
    if conversion_demo_pct:
        sdr.conversion_demo_pct = conversion_demo_pct

    db.session.commit()

    return True, "Success"


def update_sdr_email_tracking_settings(
    client_sdr_id: int,
    track_open: Optional[bool] = None,
    track_link: Optional[bool] = None,
) -> bool:
    """Updates the email tracking settings for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR
        track_open (Optional[bool], optional): Whether to track email opens. Defaults to None.
        track_link (Optional[bool], optional): Whether or not to track link clicks. Defaults to None.

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the Client SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    # Update the Client SDR
    if track_open is not None:
        sdr.email_open_tracking_enabled = track_open
    if track_link is not None:
        sdr.email_link_tracking_enabled = track_link

    db.session.commit()

    return True


def get_sdr_send_statistics(client_sdr_id: int) -> dict:
    """Gets the send statistics for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        dict: The send statistics for the Client SDR
    """
    from sqlalchemy import func

    # Get the Client SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    # Get how many were sent in the last 7 days
    query = """
        SELECT
            count(g.*) FILTER (WHERE g.message_status = 'SENT'
                AND g.message_type = 'LINKEDIN'
                AND g.date_sent > now() - Interval '7 days')
        FROM
            client_sdr AS s
            LEFT JOIN client AS c ON c.id = s.client_id
            LEFT JOIN outbound_campaign AS oc ON s.id = oc.client_sdr_id
            LEFT JOIN generated_message AS g 
                ON g.outbound_campaign_id = oc.id and 
                    g.message_status = 'SENT' and 
                    g.message_type = 'LINKEDIN'
        WHERE
            s.active
            AND c.active
            AND s.id = :client_sdr_id
            AND g.date_sent > s.created_at
            AND g.message_status = 'SENT'
            and g.message_type = 'LINKEDIN'
            AND g.date_sent > s.created_at;
    """
    results = db.session.execute(query, {"client_sdr_id": client_sdr_id}).fetchall()
    last_7_days_count = results[0][0] if results else 0

    # Get all time
    query = """
        SELECT
            count(g.*) FILTER (WHERE g.message_status = 'SENT'
                AND g.message_type = 'LINKEDIN')
        FROM
            client_sdr AS s
            LEFT JOIN client AS c ON c.id = s.client_id
            LEFT JOIN outbound_campaign AS oc ON s.id = oc.client_sdr_id
            LEFT JOIN generated_message AS g 
                ON g.outbound_campaign_id = oc.id and 
                    g.message_status = 'SENT' and 
                    g.message_type = 'LINKEDIN'
        WHERE
            s.active
            AND c.active
            AND s.id = :client_sdr_id
            AND g.message_status = 'SENT'
            and g.message_type = 'LINKEDIN'
            AND g.date_sent > s.created_at;
    """
    results = db.session.execute(query, {"client_sdr_id": client_sdr_id}).fetchall()
    all_time_count = results[0][0] if results else 0

    return {
        "last_7_days": last_7_days_count,
        "all_time": all_time_count,
    }


def get_active_sdrs(client_sdr_id: int) -> list[dict]:
    """Gets all active SDRs for a given Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        list[dict]: The active SDRs for the Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get all active SDRs
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.client_id == sdr.client_id, ClientSDR.active == True
    ).all()

    # Convert to dicts
    sdr_dicts = []
    for sdr in sdrs:
        sdr_dicts.append(sdr.to_dict())

    return sdr_dicts
