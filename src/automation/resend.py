import datetime
import os
import resend

resend.api_key = "re_bFWa8smr_9pFd7krp6MnnUAYmvF1KYDDv"


def send_email(html: str):
    params = {
        "from": "ai@sellscale.com",
        "to": ["aakash@sellscale.com"],
        "subject": "[MOCK DATA] Weekly Report - {date}".format(
            date=datetime.datetime.now().strftime("%Y-%m-%d")
        ),
        "html": html,
    }

    email = resend.Emails.send(params)
    return email
