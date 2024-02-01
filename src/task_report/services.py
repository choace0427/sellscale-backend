import datetime
from app import db
from src.automation.resend import send_email
from src.client.models import ClientSDR
from src.task_report.task_reminder_email_template import generate_task_report_html
from src.weekly_report.email_template import (
    generate_weekly_update_email,
)

from src.weekly_report.models import *


def send_task_report_email(
    client_sdr_id: int,
    test_mode: bool = True,
    to_emails: list[str] = [],
    cc_emails: list[str] = [],
    bcc_emails: list[str] = [],
) -> bool:
    html = generate_task_report_html(client_sdr_id=client_sdr_id)

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    first_name = client_sdr.name.split(" ")[0]

    date_in_title = datetime.datetime.now().strftime("%B %-d")
    title = "Action Needed: Review {first_name}'s tasks {date_in_title}".format(
        first_name=first_name, date_in_title=date_in_title
    )

    send_email(
        html=html,
        title=title,
        to_emails=to_emails,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
    )

    return True
