import datetime
import os
import resend

resend.api_key = "re_bFWa8smr_9pFd7krp6MnnUAYmvF1KYDDv"


def send_email(html: str, title: str, to_emails: list[str] = []):
    params = {
        "from": "ai@sellscale.com",
        "to": to_emails,
        "subject": title,
        "html": html,
    }

    email = resend.Emails.send(params)
    return email
