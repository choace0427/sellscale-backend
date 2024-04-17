import json
import requests
import os
from typing import Optional, Union
from datetime import datetime, timezone

from app import db, celery
from src.client.models import ClientSDR, Client
from src.client.sdr.email.models import SDREmailBank
from src.client.sdr.email.services_email_bank import email_belongs_to_sdr
from src.email_outbound.models import (
    EmailConversationMessage,
    EmailConversationThread,
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
    ProspectEmailStatusRecords,
)
from src.prospecting.models import Prospect
from src.prospecting.services import calculate_prospect_overall_status
from src.prospecting.nylas.nylas_wrappers import wrapped_nylas_get_threads
from src.message_generation.services import process_generated_msg_queue

UNSUBSCRIBE_WEBSITE_URL = os.environ.get("UNSUBSCRIBE_WEBSITE_URL")


NYLAS_THREAD_LIMIT = 10


def nylas_get_threads(
    client_sdr_id: int, prospect_id: int, limit: int, offset: int
) -> list[dict]:
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

    threads: list[EmailConversationThread] = (
        EmailConversationThread.query.filter_by(
            client_sdr_id=client_sdr_id, prospect_id=prospect_id
        )
        .order_by(EmailConversationThread.last_message_timestamp.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

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

    # Get all Emails that belong to the SDR and are in the email bank
    emails: list[SDREmailBank] = SDREmailBank.query.filter_by(
        client_sdr_id=client_sdr_id
    ).all()

    # Loop through the emails that belong to the SDR
    for email in emails:
        # If the email is not nylas connected, then we continue
        if (
            not email.nylas_active
            or not email.nylas_auth_code
            or not email.nylas_account_id
        ):
            continue

        # Get the threads from Nylas
        result = wrapped_nylas_get_threads(email.nylas_auth_code, prospect.email, limit)

        # Update old / add new threads
        for thread in result:
            existing_thread: EmailConversationThread = (
                EmailConversationThread.query.filter_by(
                    nylas_thread_id=thread.get("id")
                ).first()
            )

            # Update existing thread
            if existing_thread:
                # Convert time-since-epoch into datetime objects
                first_message_timestamp = existing_thread.first_message_timestamp
                last_message_received_timestamp = (
                    existing_thread.last_message_received_timestamp
                )
                last_message_sent_timestamp = (
                    existing_thread.last_message_sent_timestamp
                )
                last_message_timestamp = existing_thread.last_message_timestamp
                if thread.get("first_message_timestamp"):
                    first_message_timestamp = datetime.fromtimestamp(
                        thread.get("first_message_timestamp"), tz=timezone.utc
                    )
                if thread.get("last_message_received_timestamp"):
                    last_message_received_timestamp = datetime.fromtimestamp(
                        thread.get("last_message_received_timestamp"), tz=timezone.utc
                    )
                if thread.get("last_message_sent_timestamp"):
                    last_message_sent_timestamp = datetime.fromtimestamp(
                        thread.get("last_message_sent_timestamp"), tz=timezone.utc
                    )
                if thread.get("last_message_timestamp"):
                    last_message_timestamp = datetime.fromtimestamp(
                        thread.get("last_message_timestamp"), tz=timezone.utc
                    )

                existing_thread.subject = thread.get("subject", existing_thread.subject)
                existing_thread.snippet = thread.get("snippet", existing_thread.snippet)
                existing_thread.first_message_timestamp = first_message_timestamp
                existing_thread.last_message_received_timestamp = (
                    last_message_received_timestamp
                )
                existing_thread.last_message_sent_timestamp = (
                    last_message_sent_timestamp
                )
                existing_thread.last_message_timestamp = last_message_timestamp
                existing_thread.participants = thread.get(
                    "participants", existing_thread.participants
                )
                existing_thread.has_attachments = thread.get(
                    "has_attachments", existing_thread.has_attachments
                )
                existing_thread.unread = thread.get("unread", existing_thread.unread)
                existing_thread.version = thread.get("version", existing_thread.version)
                existing_thread.nylas_thread_id = thread.get(
                    "id", existing_thread.nylas_thread_id
                )
                existing_thread.nylas_message_ids = thread.get(
                    "message_ids", existing_thread.nylas_message_ids
                )
                existing_thread.nylas_data_raw = thread

            # Add new thread
            if not existing_thread:
                # Convert time-since-epoch into datetime objects
                first_message_timestamp = None
                last_message_received_timestamp = None
                last_message_sent_timestamp = None
                last_message_timestamp = None
                if thread.get("first_message_timestamp"):
                    first_message_timestamp = datetime.fromtimestamp(
                        thread.get("first_message_timestamp"), tz=timezone.utc
                    )
                if thread.get("last_message_received_timestamp"):
                    last_message_received_timestamp = datetime.fromtimestamp(
                        thread.get("last_message_received_timestamp"), tz=timezone.utc
                    )
                if thread.get("last_message_sent_timestamp"):
                    last_message_sent_timestamp = datetime.fromtimestamp(
                        thread.get("last_message_sent_timestamp"), tz=timezone.utc
                    )
                if thread.get("last_message_timestamp"):
                    last_message_timestamp = datetime.fromtimestamp(
                        thread.get("last_message_timestamp"), tz=timezone.utc
                    )

                new_thread: EmailConversationThread = EmailConversationThread(
                    client_sdr_id=client_sdr_id,
                    prospect_id=prospect.id,
                    prospect_email=prospect.email,
                    sdr_email=email.email_address,
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


def nylas_update_single_thread(thread_id: str, thread: Optional[dict] = {}) -> bool:
    """Updates a single thread based on the thread_id, or if the thread is supplied, update the thread in DB.

    Args:
        thread_id (str): ID of the thread from Nylas
        thread (Optional[dict], optional): The thread, if we have the information and are looking to update. Defaults to {}.

    Returns:
        bool: Whether the update was successful
    """
    if thread:
        existing_thread: EmailConversationThread = (
            EmailConversationThread.query.filter_by(
                nylas_thread_id=thread.get("id")
            ).first()
        )

        if not existing_thread:
            return False

        # Convert time-since-epoch into datetime objects
        first_message_timestamp = existing_thread.first_message_timestamp
        last_message_received_timestamp = (
            existing_thread.last_message_received_timestamp
        )
        last_message_sent_timestamp = existing_thread.last_message_sent_timestamp
        last_message_timestamp = existing_thread.last_message_timestamp
        if thread.get("first_message_timestamp"):
            first_message_timestamp = datetime.fromtimestamp(
                thread.get("first_message_timestamp"), tz=timezone.utc
            )
        if thread.get("last_message_received_timestamp"):
            last_message_received_timestamp = datetime.fromtimestamp(
                thread.get("last_message_received_timestamp"), tz=timezone.utc
            )
        if thread.get("last_message_sent_timestamp"):
            last_message_sent_timestamp = datetime.fromtimestamp(
                thread.get("last_message_sent_timestamp"), tz=timezone.utc
            )
        if thread.get("last_message_timestamp"):
            last_message_timestamp = datetime.fromtimestamp(
                thread.get("last_message_timestamp"), tz=timezone.utc
            )

        existing_thread.subject = thread.get("subject", existing_thread.subject)
        existing_thread.snippet = thread.get("snippet", existing_thread.snippet)
        existing_thread.first_message_timestamp = first_message_timestamp
        existing_thread.last_message_received_timestamp = (
            last_message_received_timestamp
        )
        existing_thread.last_message_sent_timestamp = last_message_sent_timestamp
        existing_thread.last_message_timestamp = last_message_timestamp
        existing_thread.participants = thread.get(
            "participants", existing_thread.participants
        )
        existing_thread.has_attachments = thread.get(
            "has_attachments", existing_thread.has_attachments
        )
        existing_thread.unread = thread.get("unread", existing_thread.unread)
        existing_thread.version = thread.get("version", existing_thread.version)
        existing_thread.nylas_thread_id = thread.get(
            "id", existing_thread.nylas_thread_id
        )
        existing_thread.nylas_message_ids = thread.get(
            "message_ids", existing_thread.nylas_message_ids
        )
        existing_thread.nylas_data_raw = thread

        db.session.commit()
        return True

    # TODO, update if we have thread id

    return True


def nylas_get_messages(
    client_sdr_id: int,
    prospect_id: int,
    nylas_account_id: Optional[str] = "",
    thread_id: Optional[str] = "",
    message_ids: Optional[list[str]] = [],
) -> list[dict]:
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
        if nylas_account_id:
            success = nylas_update_messages(
                client_sdr_id=client_sdr_id,
                nylas_account_id=nylas_account_id,
                prospect_id=prospect_id,
                thread_id=thread_id,
                message_ids=message_ids,
            )
        else:
            # Get all emails from the bank
            emails: list[SDREmailBank] = SDREmailBank.query.filter(
                SDREmailBank.client_sdr_id == client_sdr_id,
                SDREmailBank.nylas_active == True,
                SDREmailBank.nylas_auth_code != None,
                SDREmailBank.nylas_account_id != None,
            ).all()
            for email in emails:
                success = nylas_update_messages(
                    client_sdr_id=client_sdr_id,
                    nylas_account_id=email.nylas_account_id,
                    prospect_id=prospect_id,
                    thread_id=thread_id,
                    message_ids=message_ids,
                )
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
        messages_raw = messages_raw.filter(
            EmailConversationMessage.nylas_message_id.in_(message_ids)
        )

    # Get messages from the ORM object
    messages: list[EmailConversationMessage] = messages_raw.order_by(
        EmailConversationMessage.date_received.desc()
    ).all()

    # Process if the messages are AI generated or not
    for message in messages:
        if message.ai_generated is None:
            process_generated_msg_queue(
                client_sdr_id=client_sdr_id,
                nylas_message_id=message.nylas_message_id,
                email_convo_entry_id=message.id,
            )

    return [message.to_dict() for message in messages]


def nylas_update_messages(
    client_sdr_id: int,
    nylas_account_id: str,
    prospect_id: int,
    thread_id: Optional[str] = "",
    message_ids: Optional[list[str]] = [],
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

    # Get the email bank value that belong to the nylas account ID
    email_bank: SDREmailBank = SDREmailBank.query.filter_by(
        client_sdr_id=client_sdr_id,
        nylas_account_id=nylas_account_id,
    ).first()

    # Get messages from Nylas
    if message_ids:
        res = requests.get(
            f'https://api.nylas.com/messages/{",".join(message_ids)}',
            headers={"Authorization": f"Bearer {email_bank.nylas_auth_code}"},
        )
    elif thread_id:
        res = requests.get(
            f"https://api.nylas.com/messages?thread_id={thread_id}",
            headers={"Authorization": f"Bearer {email_bank.nylas_auth_code}"},
        )
    else:
        return {}
    if res.status_code != 200:
        return False

    result = res.json()

    # Update existing or create new messages
    if type(result) == dict:
        process_nylas_update_message_result(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            email_bank_id=email_bank.id,
            message=result,
        )
    elif type(result) == list:
        for message in result:
            process_nylas_update_message_result(
                client_sdr_id=client_sdr_id,
                prospect_id=prospect_id,
                email_bank_id=email_bank.id,
                message=message,
            )
    else:
        return False

    # Get the latest message and update the prospect accordingly
    latest_message: EmailConversationMessage = (
        EmailConversationMessage.query.filter_by(prospect_id=prospect_id)
        .order_by(EmailConversationMessage.date_received.desc())
        .first()
    )
    prospect.email_last_message_timestamp = latest_message.date_received
    prospect.email_is_last_message_from_sdr = latest_message.from_sdr
    prospect.email_last_message_from_prospect = (
        None if latest_message.from_sdr else latest_message.body
    )
    prospect.email_last_message_from_sdr = (
        latest_message.body if latest_message.from_sdr else None
    )

    db.session.commit()

    return True


def process_nylas_update_message_result(
    client_sdr_id: int, prospect_id: int, email_bank_id: int, message: dict
) -> bool:
    """Processes the result of a Nylas update message call.

    Args:
        client_sdr_id (int): ID of the ClientSDR
        prospect_id (int): ID of the Prospect
        email_bank_id (int): ID of the email bank
        message (dict): Message from Nylas

    Returns:
        bool: Whether the processing was successful
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    email_bank: SDREmailBank = SDREmailBank.query.get(email_bank_id)

    existing_message: EmailConversationMessage = (
        EmailConversationMessage.query.filter_by(
            nylas_message_id=message.get("id")
        ).first()
    )

    # Get existing thread (one should exist)
    existing_thread: EmailConversationThread = EmailConversationThread.query.filter_by(
        nylas_thread_id=message.get("thread_id")
    ).first()
    if not existing_thread:
        raise Exception(
            f'No thread found for message {message.get("subject")} in SDR: {client_sdr_id}'
        )

    # Update existing message
    if existing_message:
        # Convert time-since-epoch into datetime objects
        date_received = existing_message.date_received
        if message.get("date"):
            date_received = datetime.fromtimestamp(
                message.get("date", existing_message.date_received) or 0,
                tz=timezone.utc,
            )

        existing_message.subject = message.get("subject", existing_message.subject)
        existing_message.snippet = message.get("snippet", existing_message.snippet)
        existing_message.body = message.get("body", existing_message.body)
        existing_message.bcc = message.get("bcc", existing_message.bcc)
        existing_message.cc = message.get("cc", existing_message.cc)
        existing_message.date_received = date_received
        existing_message.files = message.get("files", existing_message.files)
        existing_message.message_from = message.get(
            "from", existing_message.message_from
        )
        existing_message.message_to = message.get("to", existing_message.message_to)
        existing_message.reply_to = message.get("reply_to", existing_message.reply_to)
        existing_message.nylas_message_id = message.get(
            "id", existing_message.nylas_message_id
        )
        existing_message.nylas_data_raw = message

    # Add new message
    if not existing_message:
        # Check if message is from SDR
        message_from_prospect = False
        message_from_sdr = False
        messages_from: list[dict] = message.get("from")
        for message_from in messages_from:
            message_from_email = message_from.get("email")
            if message_from_email == prospect.email:
                message_from_prospect = True
            elif email_belongs_to_sdr(
                client_sdr_id=client_sdr_id, email_address=message_from_email
            ):
                message_from_sdr = True

        # Convert time-since-epoch into datetime objects
        date_received = None
        if message.get("date"):
            date_received = datetime.fromtimestamp(
                message.get("date", 0) or 0, tz=timezone.utc
            )

        new_message: EmailConversationMessage = EmailConversationMessage(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            prospect_email=prospect.email,
            sdr_email=email_bank.email_address,
            from_sdr=message_from_sdr,
            from_prospect=message_from_prospect,
            subject=message.get("subject"),
            snippet=message.get("snippet"),
            body=message.get("body"),
            bcc=message.get("bcc"),
            cc=message.get("cc"),
            date_received=date_received,
            files=message.get("files"),
            message_from=message.get("from"),
            message_to=message.get("to"),
            reply_to=message.get("reply_to"),
            email_conversation_thread_id=existing_thread.id,
            nylas_message_id=message.get("id"),
            nylas_data_raw=message,
            nylas_thread_id=message.get("thread_id"),
        )
        db.session.add(new_message)

        # Increment unread messages
        prospect.email_unread_messages = (
            prospect.email_unread_messages + 1 if prospect.email_unread_messages else 1
        )

    db.session.commit()

    return True


def nylas_send_email(
    client_sdr_id: int,
    prospect_id: int,
    subject: str,
    body: str,
    reply_to_message_id: Union[str, None] = None,
    prospect_email_id: Optional[int] = None,
    email_bank_id: Optional[int] = None,
    bcc: Optional[list[str]] = None,
    cc: Optional[list[str]] = None,
) -> dict:
    """Sends an email to the Prospect through the ClientSDR's Nylas account.

    Args:
        - client_sdr_id (int): ID of the ClientSDR sending the email
        - prospect_id (int): ID of the Prospect receiving the email
        - subject (str): Subject of the email
        - body (str): Body of the email
        - reply_to_message_id (str, optional): ID of the message to reply to
        - prospect_email_id (Optional[int], optional): ID of the ProspectEmail record. Defaults to None.

    Returns:
        - dict: Response from Nylas API
    """
    if not prospect_email_id:
        prospect_email: ProspectEmail = ProspectEmail(
            prospect_id=prospect_id,
            email_status=ProspectEmailStatus.APPROVED,
            outreach_status=ProspectEmailOutreachStatus.NOT_SENT,
        )
        db.session.add(prospect_email)
        db.session.commit()
        prospect_email_id = prospect_email.id
    else:
        prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
        prospect_email_id = prospect_email.id

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_prospect_email_id = prospect_email_id
    db.session.add(prospect)
    db.session.commit()

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Construct the tracking payload
    tracking_payload = {
        "prospect_id": prospect_id,
        "prospect_email_id": prospect_email_id,
        "client_sdr_id": client_sdr_id,
    }
    tracking_payload_json: str = json.dumps(tracking_payload)

    client: Client = Client.query.get(client_sdr.client_id)

    # Add an unsubscribe link to the body
    # TODO: This should only send unsubscribe link iff we are below ACTIVE_CONVO
    unsubscribe_url = str(UNSUBSCRIBE_WEBSITE_URL) + "/unsubscribe/"
    client_uuid = client.uuid if client.uuid else client.regenerate_uuid()
    sdr_uuid = client_sdr.uuid if client_sdr.uuid else client_sdr.regenerate_uuid()
    prospect_uuid = prospect.uuid if prospect.uuid else prospect.regenerate_uuid()
    query_params = f"?c={client_uuid}&s={sdr_uuid}&p={prospect_uuid}"
    link = unsubscribe_url + query_params

    # todo(Aakash) uncomment this to bring back Unsubscribe!
    # if not reply_to_message_id:
    #     body += f"</br></br><a href='{link}' target='_blank'>Unsubscribe</a>"

    # Get the email bank value (first for now)
    email_bank: SDREmailBank = None
    if email_bank_id:
        email_bank: SDREmailBank = SDREmailBank.query.get(email_bank_id)
    if not email_bank:
        email_bank: SDREmailBank = SDREmailBank.query.filter(
            SDREmailBank.client_sdr_id == client_sdr_id,
            SDREmailBank.nylas_active == True,
            SDREmailBank.nylas_auth_code != None,
            SDREmailBank.nylas_account_id != None,
        ).first()

    if not email_bank:
        raise Exception("No EmailBank found in nylas_send_email.")

    # Send email through Nylas
    res = requests.post(
        url=f"https://api.nylas.com/send",
        headers={
            "Authorization": f"Bearer {email_bank.nylas_auth_code}",
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
                    "email": email_bank.email_address,
                    "name": client_sdr.name,
                }
            ],
            "bcc": [{"name": _bcc, "email": _bcc} for _bcc in bcc] if bcc else [],
            "cc": [{"name": _cc, "email": _cc} for _cc in cc] if cc else [],
            "reply_to_message_id": reply_to_message_id,
            "tracking": {  # Track opens and thread replies
                "opens": True,
                "thread_replies": True,
                "payload": tracking_payload_json,
            },
        },
    )
    if res.status_code != 200:
        print(res.json())
        return {}

    result = res.json()

    # Add to ProspectEmail record
    prospect_email.nylas_thread_id = result.get("thread_id")

    # Change ProspectEmail status to "SENT"
    prospect_email = ProspectEmail.query.get(prospect_email_id)
    prospect_email.outreach_status = ProspectEmailOutreachStatus.SENT_OUTREACH
    prospect_email.email_status = ProspectEmailStatus.SENT
    db.session.add(prospect_email)
    db.session.commit()

    # Create a ProspectEmailStatusRecord
    prospect_email_status_record: ProspectEmailStatusRecords = (
        ProspectEmailStatusRecords(
            prospect_email_id=prospect_email_id,
            from_status=ProspectEmailOutreachStatus.NOT_SENT,
            to_status=ProspectEmailOutreachStatus.SENT_OUTREACH,
            automated=True,
        )
    )
    db.session.add(prospect_email_status_record)
    db.session.commit()

    # Calculate overall status
    calculate_prospect_overall_status(prospect_id)

    return result


def get_email_messages_with_prospect(
    client_sdr_id: int, prospect_id: int, thread_id: str, x: Optional[int] = None
) -> list:
    """Gets the messages between a ClientSDR and a Prospect. Optionally, can limit the number of messages returned.

    Args:
        - client_sdr_id (int): ID of the ClientSDR
        - prospect_id (int): ID of the Prospect
        - thread_id (int): ID of the EmailConversationThread
        - x (int, optional): Number of messages to return

    Returns:
    """
    messages: EmailConversationMessage = EmailConversationMessage.query.filter(
        EmailConversationMessage.client_sdr_id == client_sdr_id,
        EmailConversationMessage.prospect_id == prospect_id,
        EmailConversationMessage.nylas_thread_id == thread_id,
    ).order_by(EmailConversationMessage.date_received.desc())

    if x:
        messages = messages.limit(x)
    messages = messages.all()

    return [message.to_dict() for message in messages]
