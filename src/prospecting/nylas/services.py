import requests
from typing import Optional
from datetime import datetime, timezone

from app import db, celery
from src.client.models import ClientSDR
from src.email_outbound.models import EmailConversationMessage, EmailConversationThread, ProspectEmail, ProspectEmailOutreachStatus, ProspectEmailStatus
from src.prospecting.models import Prospect
from src.prospecting.services import calculate_prospect_overall_status

NYLAS_THREAD_LIMIT = 10


def nylas_get_threads(client_sdr_id: int, prospect_id: int, limit: int, offset: int) -> list[dict]:
    """Gets the email threads between the ClientSDR and Prospect.

    Args:
        - client_sdr_id (int): ID of the ClientSDR
        - prospect_id (int): ID of the Prospect
        - limit (int): Number of threads to return
        - offset (int): Offset of threads to return

    Returns:
        - list: List of email threads
    """
    try:
        success = nylas_update_threads(client_sdr_id, prospect_id, NYLAS_THREAD_LIMIT)
    except:
        success = False

    threads: list[EmailConversationThread] = EmailConversationThread.query.filter_by(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id
    ).limit(limit).offset(offset).all()

    return [thread.to_dict() for thread in threads]


def nylas_update_threads(client_sdr_id: int, prospect_id: int, limit: int) -> bool:
    """Makes a call to Nylas to get email threads, updating or creating new records in the database.

    Args:
        - client_sdr_id (int): ID of the ClientSDR
        - prospect_id (int): ID of the Prospect
        - limit (int): Number of threads to return

    Returns:
        - bool: Whether the call was successful
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    print(prospect, client_sdr)

    # Get threads from Nylas
    res = requests.get(
        f"https://api.nylas.com/threads?limit={limit}&any_email={prospect.email}",
        headers={"Authorization": f"Bearer {client_sdr.nylas_auth_code}"},
    )
    if res.status_code != 200:
        return False

    result: list[dict] = res.json()

    # Update old / add new threads
    for thread in result:
        existing_thread: EmailConversationThread = EmailConversationThread.query.filter_by(
            nylas_thread_id=thread.get("id")
        ).first()

        # Update existing thread
        if existing_thread:
            # Convert time-since-epoch into datetime objects
            first_message_timestamp = datetime.fromtimestamp(thread.get("first_message_timestamp", existing_thread.first_message_timestamp) or 0, tz=timezone.utc)
            last_message_received_timestamp = datetime.fromtimestamp(thread.get("last_message_received_timestamp", existing_thread.last_message_received_timestamp) or 0, tz=timezone.utc)
            last_message_sent_timestamp = datetime.fromtimestamp(thread.get("last_message_sent_timestamp", existing_thread.last_message_sent_timestamp) or 0, tz=timezone.utc)
            last_message_timestamp = datetime.fromtimestamp(thread.get("last_message_timestamp", existing_thread.last_message_timestamp) or 0, tz=timezone.utc)

            existing_thread.subject = thread.get("subject", existing_thread.subject)
            existing_thread.snippet = thread.get("snippet", existing_thread.snippet)
            existing_thread.first_message_timestamp = first_message_timestamp
            existing_thread.last_message_received_timestamp = last_message_received_timestamp
            existing_thread.last_message_sent_timestamp = last_message_sent_timestamp
            existing_thread.last_message_timestamp = last_message_timestamp
            existing_thread.participants = thread.get("participants", existing_thread.participants)
            existing_thread.has_attachments = thread.get("has_attachments", existing_thread.has_attachments)
            existing_thread.unread = thread.get("unread", existing_thread.unread)
            existing_thread.version = thread.get("version", existing_thread.version)
            existing_thread.nylas_thread_id = thread.get("id", existing_thread.nylas_thread_id)
            existing_thread.nylas_message_ids = thread.get("message_ids", existing_thread.nylas_message_ids)
            existing_thread.nylas_data_raw = thread

        # Add new thread
        if not existing_thread:
            # Convert time-since-epoch into datetime objects
            first_message_timestamp = datetime.fromtimestamp(thread.get("first_message_timestamp" or 0, 0), tz=timezone.utc)
            last_message_received_timestamp = datetime.fromtimestamp(thread.get("last_message_received_timestamp" or 0, 0), tz=timezone.utc)
            last_message_sent_timestamp = datetime.fromtimestamp(thread.get("last_message_sent_timestamp", 0) or 0, tz=timezone.utc)
            last_message_timestamp = datetime.fromtimestamp(thread.get("last_message_timestamp" or 0, 0), tz=timezone.utc)

            new_thread: EmailConversationThread = EmailConversationThread(
                client_sdr_id=client_sdr_id,
                prospect_id=prospect.id,
                prospect_email=prospect.email,
                sdr_email=client_sdr.email,
                subject=thread.get("subject"),
                snippet=thread.get("snippet"),
                first_message_timestamp=first_message_timestamp,
                last_message_received_timestamp=last_message_received_timestamp,
                last_message_sent_timestamp=last_message_sent_timestamp,
                last_message_timestamp=last_message_timestamp,
                participants=thread.get("participants"),
                has_attachments=thread.get("has_attachments"),
                unread=thread.get("unread"),
                version=thread.get("version"),
                nylas_thread_id=thread.get("id"),
                nylas_message_ids=thread.get("message_ids"),
                nylas_data_raw=thread,
            )
            db.session.add(new_thread)

    db.session.commit()

    return True


def nylas_get_messages(client_sdr_id: int, prospect_id: int, thread_id: Optional[str] = "", message_ids: Optional[list[str]] = []) -> list[dict]:
    """Gets the email messages between the ClientSDR and Prospect.

    Args:
        - client_sdr_id (int): ID of the ClientSDR
        - prospect_id (int): ID of the Prospect
        - thread_id (Optional[str], optional): ID of the thread. Defaults to "".
        - message_ids (Optional[list], optional): List of message IDs. Defaults to [].

    Returns:
        - list: List of email messages
    """
    try:
        success = nylas_update_messages(client_sdr_id, prospect_id, thread_id, message_ids)
    except:
        success = False

    # Get messages from database. This is a raw ORM object.
    messages_raw = EmailConversationMessage.query.filter_by(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id
    )

    # Filter by thread_id or message_ids, if provided
    if thread_id:
        messages_raw = messages_raw.filter_by(nylas_thread_id=thread_id)
    if message_ids:
        messages_raw = messages_raw.filter(EmailConversationMessage.nylas_message_id.in_(message_ids))

    # Get messages from the ORM object
    messages: list[EmailConversationMessage] = messages_raw.all()

    return [message.to_dict() for message in messages]


def nylas_update_messages(
    client_sdr_id: int, prospect_id: int, thread_id: Optional[str] = "", message_ids: Optional[list[str]] = []
) -> bool:
    """Makes a call to Nylas to get email messages, updating or creating new records in the database.

    Args:
        - client_sdr_id (int): ID of the ClientSDR
        - prospect_id (int): ID of the Prospect
        - thread_id (Optional[str], optional): ID of the thread. Defaults to "".
        - message_ids (Optional[list], optional): List of message IDs. Defaults to [].

    Returns:
        - bool: Whether the call was successful
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get messages from Nylas
    if message_ids:
        res = requests.get(
            f'https://api.nylas.com/messages/{",".join(message_ids)}',
            headers={"Authorization": f"Bearer {client_sdr.nylas_auth_code}"},
        )
    elif thread_id:
        res = requests.get(
            f"https://api.nylas.com/messages?thread_id={thread_id}",
            headers={"Authorization": f"Bearer {client_sdr.nylas_auth_code}"},
        )
    else:
        return {}
    if res.status_code != 200:
        return False

    result: list[dict] = res.json()

    # Update existing or create new messages
    for message in result:
        existing_message: EmailConversationMessage = EmailConversationMessage.query.filter_by(
            nylas_message_id=message.get("id")
        ).first()

        # Update existing message
        if existing_message:
            # Convert time-since-epoch into datetime objects
            date_received = datetime.fromtimestamp(message.get("date", existing_message.date_received) or 0, tz=timezone.utc)

            existing_message.subject = message.get("subject", existing_message.subject)
            existing_message.snippet = message.get("snippet", existing_message.snippet)
            existing_message.body = message.get("body", existing_message.body)
            existing_message.bcc = message.get("bcc", existing_message.bcc)
            existing_message.cc = message.get("cc", existing_message.cc)
            existing_message.date_received = date_received
            existing_message.files = message.get("files", existing_message.files)
            existing_message.message_from = message.get("from", existing_message.message_from)
            existing_message.message_to = message.get("to", existing_message.message_to)
            existing_message.reply_to = message.get("reply_to", existing_message.reply_to)
            existing_message.email_conversation_thread_id = message.get(
                "thread_id", existing_message.email_conversation_thread_id
            )
            existing_message.nylas_message_id = message.get("id", existing_message.nylas_message_id)
            existing_message.nylas_data_raw = message

        # Add new message
        if not existing_message:
            # Check if message is from SDR
            message_from_sdr = False
            messages_from: list[dict] = message.get("from")
            for message_from in messages_from:
                message_from_email = message_from.get("email")
                if message_from_email == client_sdr.email:
                    message_from_sdr = True

            # Get existing thread (one should exist)
            existing_thread: EmailConversationThread = (
                EmailConversationThread.query.filter_by(
                    nylas_thread_id=message.get("thread_id")
                ).first()
            )
            if not existing_thread:
                raise Exception(
                    f'No thread found for message {message.get("subject")} in SDR: {client_sdr_id}'
                )

            # Convert time-since-epoch into datetime objects
            date_received = datetime.fromtimestamp(message.get("date", 0) or 0, tz=timezone.utc)

            new_message: EmailConversationMessage = EmailConversationMessage(
                client_sdr_id = client_sdr_id,
                prospect_id = prospect_id,
                prospect_email = prospect.email,
                sdr_email = client_sdr.email,
                from_sdr = message_from_sdr,
                subject = message.get("subject"),
                snippet = message.get("snippet"),
                body = message.get("body"),
                bcc = message.get("bcc"),
                cc = message.get("cc"),
                date_received = date_received,
                files = message.get("files"),
                message_from = message.get("from"),
                message_to = message.get("to"),
                reply_to = message.get("reply_to"),
                email_conversation_thread_id = existing_thread.id,
                nylas_message_id = message.get("id"),
                nylas_data_raw = message,
            )
            db.session.add(new_message)

    db.session.commit()

    return True


def nylas_send_email(client_sdr_id: int, prospect_id: int, subject: str, body: str) -> dict:
    """Sends an email to the Prospect through the ClientSDR's Nylas account.

    Args:
        - client_sdr_id (int): ID of the ClientSDR sending the email
        - prospect_id (int): ID of the Prospect receiving the email
        - subject (str): Subject of the email
        - body (str): Body of the email

    Returns:
        - dict: Response from Nylas API
    """

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect.approved_prospect_email_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    res = requests.post(
        url=f"https://api.nylas.com/send",
        headers={
            "Authorization": f"Bearer {client_sdr.nylas_auth_code}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "subject": subject,
            "body": body,
            "to": [
                {
                    "email": prospect.email,
                    "name": prospect.full_name,
                }
            ],
            "from": [
                {
                    "email": client_sdr.email,
                    "name": client_sdr.name,
                }
            ],
        },
    )
    if res.status_code != 200:
        return {}

    result = res.json()

    # Add to ProspectEmail record
    prospect_email.nylas_thread_id = result.get("thread_id")

    # Change ProspectEmail status to "SENT"
    prospect_email.outreach_status = ProspectEmailOutreachStatus.SENT_OUTREACH
    prospect_email.email_status = ProspectEmailStatus.SENT

    db.session.commit()

    # Calculate overall status
    calculate_prospect_overall_status(prospect_id)

    return result