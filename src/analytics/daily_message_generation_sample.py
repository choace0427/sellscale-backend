import json
from app import db, celery
from datetime import datetime
import html
from src.automation.resend import send_email


def fetch_data():
    query = """
    select 
        prospect.full_name,
        prospect.id,
        prospect.company,
        prospect.title,
        prospect.linkedin_url,
        completion,
        date_sent,
        generated_message.completion as message
    from generated_message
        join prospect on prospect.id = generated_message.prospect_id
    where generated_message.created_at > NOW() - '24 hours'::INTERVAL
        and message_status = 'SENT'
        and message_type = 'LINKEDIN'
    order by random()
    limit 10;
    """
    return db.session.execute(query).fetchall()


def format_row(row):
    return """
    <tr style="border: 1px solid gray; margin-bottom: 4px;">
        <td>
            <p>
                <a href="{linkedin_url}" target="_blank" style="font-weight: bold; text-decoration: none; color: black;">{full_name}</a><br>
                <span style="color: gray;">{title} @ {company}</span>
            </p>
        </td>
        <td>{date_sent}</td>
        <td style="border: 1px solid gray; border-radius: 4px; padding: 4px;">{message}</td>
    </tr>
    """.format(
        linkedin_url=html.escape(row.linkedin_url),
        full_name=html.escape(row.full_name),
        company=html.escape(row.company),
        title=html.escape(row.title),
        date_sent=row.date_sent.strftime("%Y-%m-%d"),
        message=html.escape(row.message),
    )


@celery.task
def send_report_email():
    data = fetch_data()
    rows = [format_row(row) for row in data]

    email_body = """
    <h1>Daily LinkedIn Message Completion Report</h1>
    <p>Here are a sample of 10 random LinkedIn messages that were sent out in the last 24 hours.</p>

    <table style="width: 100%; border-collapse: collapse; border: 1px solid #ccc;">
        <tr style="background-color: #eee;">
            <th>Prospect & Details</th>
            <th style="width: 100px;">Date Sent</th>
            <th>Message</th>
        </tr>
        {}
    </table>
    """.format(
        "".join(rows)
    )

    send_email(
        html=email_body,
        title="Daily LinkedIn Message Completion Report",
        to_emails=["team@sellscale.com"],
    )
