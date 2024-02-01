import datetime
from app import db
from src.automation.resend import send_email
from src.client.models import ClientSDR
from src.operator_dashboard.models import OperatorDashboardEntry
from src.task_report.task_reminder_email_template import generate_task_report_html
from src.weekly_report.email_template import (
    generate_weekly_update_email,
)

from src.weekly_report.models import *


def send_all_pending_task_report_emails(to_emails: list[str] = []) -> bool:
    query = """
    select 
        client_sdr.id, client_sdr.name, count(distinct operator_dashboard_entry.id)
    from client_sdr
        join operator_dashboard_entry on operator_dashboard_entry.client_sdr_id = client_sdr.id
        join client on client.id = client_sdr.client_id
    where operator_dashboard_entry.status = 'PENDING'
        and client.active and client_sdr.active
    group by 1,2;
    """
    client_sdrs = db.session.execute(query).fetchall()

    client_sdr_ids = [(c[0], c[1]) for c in client_sdrs]

    for entry in client_sdr_ids:
        id = entry[0]
        name = entry[1]
        print(f"Sending task report email to {name}...")
        send_task_report_email(
            client_sdr_id=id,
            test_mode_to_emails=to_emails,
        )

    return True


def send_task_report_email(
    client_sdr_id: int,
    test_mode_to_emails: list[str] = [],
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

    if test_mode_to_emails:
        to_emails = test_mode_to_emails
        cc_emails = []
        bcc_emails = []

    send_email(
        html=html,
        title=title,
        to_emails=to_emails,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
    )

    return True
