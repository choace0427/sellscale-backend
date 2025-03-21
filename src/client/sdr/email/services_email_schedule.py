from typing import Optional
from app import db

from datetime import time
from src.client.models import ClientSDR

from src.client.sdr.email.models import SDREmailSendSchedule


def create_default_sdr_email_send_schedule(
    client_sdr_id: int,
    email_bank_id: int,
) -> int:
    """ Creates a default SDR Email Send Schedule

    Args:
        client_sdr_id (int): ID of the Client SDR
        email_bank_id (int): ID of the email bank

    Returns:
        int: ID of the created email send schedule
    """
    sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    email_send_schedule = SDREmailSendSchedule(
        client_sdr_id=client_sdr_id,
        email_bank_id=email_bank_id,
        time_zone=sdr.timezone or "America/Los_Angeles",
        days=[1, 2, 3, 4, 5],
        start_time=time(hour=9, minute=0),
        end_time=time(hour=17, minute=0),
    )
    db.session.add(email_send_schedule)
    db.session.commit()

    return email_send_schedule.id


def create_sdr_email_send_schedule(
    client_sdr_id: int,
    email_bank_id: int,
    time_zone: str,
    days: list[int],
    start_time: time,
    end_time: time,
) -> int:
    """ Creates an SDR Email Send Schedule

    Args:
        client_sdr_id (int): ID of the Client SDR
        email_bank_id (int): ID of the email bank
        time_zone (str): Time zone
        days (list[int]): Days to send email
        start_time (time): Start time to send email
        end_time (time): End time to send email

    Returns:
        int: ID of the created email send schedule
    """
    email_send_schedule = SDREmailSendSchedule(
        client_sdr_id=client_sdr_id,
        email_bank_id=email_bank_id,
        time_zone=time_zone,
        days=days,
        start_time=start_time,
        end_time=end_time,
    )
    db.session.add(email_send_schedule)
    db.session.commit()

    return email_send_schedule.id


def update_sdr_email_send_schedule(
    client_sdr_id: int,
    send_schedule_id: Optional[int] = None,
    time_zone: Optional[str] = None,
    days: Optional[list[int]] = None,
    start_time: Optional[time] = None,
    end_time: Optional[time] = None,
) -> bool:
    """ Edits an SDR Email Send Schedule

    Args:
        client_sdr_id (int): ID of the Client SDR
        send_schedule_id (Optional[int], optional): ID of the email send schedule. Defaults to None.
        time_zone (Optional[str], optional): Time zone. Defaults to None.
        days (Optional[list[int]], optional): Days to send email. Defaults to None.
        start_time (Optional[time], optional): Start time to send email. Defaults to None.
        end_time (Optional[time], optional): End time to send email. Defaults to None.

    Returns:
        bool: Whether or not the email send schedule was edited
    """
    schedules: list[SDREmailSendSchedule] = SDREmailSendSchedule.query.filter(
        SDREmailSendSchedule.client_sdr_id == client_sdr_id
    ).all()

    # If send_schedule_id is specified, we can just edit that one
    if send_schedule_id:
        schedule: SDREmailSendSchedule = SDREmailSendSchedule.query.filter(
            SDREmailSendSchedule.id == send_schedule_id,
            SDREmailSendSchedule.client_sdr_id == client_sdr_id
        ).first()
        schedules = [schedule]

    if not schedules:
        return False

    for schedule in schedules:
        if time_zone:
            schedule.time_zone = time_zone
        if days:
            schedule.days = days
        if start_time:
            schedule.start_time = start_time
        if end_time:
            schedule.end_time = end_time

    db.session.commit()

    return True
