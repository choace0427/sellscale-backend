import datetime
import os
import resend

resend.api_key = "re_bFWa8smr_9pFd7krp6MnnUAYmvF1KYDDv"


def send_email(
    html: str,
    title: str,
    to_emails: list[str] = [],
    cc_emails: list[str] = [],
    bcc_emails: list[str] = [],
    from_email: str = "ai@sellscale.com",
):
    params = {
        "from": from_email,
        "to": to_emails,
        "subject": title,
        "html": html,
        "cc": cc_emails,
        "bcc": bcc_emails,
    }

    email = resend.Emails.send(params)
    return email
