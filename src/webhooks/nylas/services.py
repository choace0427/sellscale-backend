import json
from typing import Union
from app import db, celery
from src.automation.slack_notification import send_status_change_slack_block
from src.client.models import ClientSDR
from src.email_outbound.models import ProspectEmail, ProspectEmailOutreachStatus
from src.email_outbound.services import update_prospect_email_outreach_status
from src.prospecting.models import Prospect, ProspectChannels

from src.prospecting.nylas.services import nylas_update_threads, nylas_get_messages
from src.prospecting.nylas.nylas_wrappers import wrapped_nylas_get_single_thread
from src.prospecting.services import calculate_prospect_overall_status
from src.webhooks.nylas.bounce_detection import is_email_bounced


@celery.task(bind=True, max_retries=5)
def process_deltas_message_created(self, deltas: Union[list[dict], dict]) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    This function processes `message.created` deltas from the `message.created` webhook.

    Args:
        deltas (list[dict]): A list of deltas from a Nylas webhook notification.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
    # Process deltas
    if type(deltas) == dict:
        process_single_message_created.apply_async(
            args=[deltas]
        )
        return True, 1

    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_message_created.apply_async(
            args=[delta]
        )

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_message_created(self, delta: dict) -> tuple[bool, str]:
    """Process a single `message.created` delta from a Nylas webhook notification.

    Args:
        delta (dict): A single `message.created` delta from a Nylas webhook notification.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the delta was processed successfully, and a string containing the id of the message that was processed, or an error message.
    """
    delta_type = delta.get('type')
    if delta_type != 'message.created':
        return False, "Delta type is not 'message.created'"

    # Get object data
    object_data: dict = delta.get('object_data')
    if not object_data:
        return False, "No object_data in delta"

    # Get the ID of the connected email account and the client SDR
    account_id: str = object_data.get('account_id')
    if not account_id:
        return False, "No account ID in object data"
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.active == True,
        ClientSDR.nylas_account_id == account_id,
        ClientSDR.nylas_active == True,
    ).first()
    if not client_sdr:
        return False, "No client SDR found"

    # TODO: DELETE THIS - HARDCODE TO SELLSCALE FOR NOW
    if client_sdr.client_id != 1:
        return False, "Client is not SellScale"

    # Get thread ID - the ID of the thread that the message belongs to
    attributes: dict = object_data.get('attributes')
    if not attributes:
        return False, "No attributes in object data"
    thread_id: str = attributes.get('thread_id')
    if not thread_id:
        return False, "No thread ID"

    # Get information about the thread
    thread: dict = wrapped_nylas_get_single_thread(
        client_sdr.nylas_auth_code, thread_id
    )

    # Check if participants include a prospect.
    # We only save threads with prospects.
    participants: list[dict] = thread.get('participants')
    if not participants:
        return False, "No participants in thread"
    participants = [participant.get('email') for participant in participants]

    prospect: Prospect = Prospect.query.filter(
        Prospect.client_id == client_sdr.client_id,
        Prospect.client_sdr_id == client_sdr.id,
        Prospect.email.in_(participants),
    ).first()
    if not prospect:
        return False, "No prospect found"
    prospect_email_id = prospect.approved_prospect_email_id
    prospect_id = prospect.id

    # Prospect was found, so we should save the thread and messages.
    result = nylas_update_threads(client_sdr.id, prospect.id, 5)
    if not result:
        return False, "Failed to save thread"

    messages: list[dict] = nylas_get_messages(client_sdr.id, prospect.id, thread.get("id"))
    for message in messages:
        # Check if message is bounced
        email_from = message.get("message_from", {'email': None}).get('email')
        bounced = is_email_bounced(email_from, message.get("body"))
        if bounced:
            # Update the Prospect's status to "BOUNCED"
            updated = update_prospect_email_outreach_status(
                prospect_email_id=prospect_email_id,
                new_status=ProspectEmailOutreachStatus.BOUNCED,
            )

            # Calculate prospect overall status
            calculate_prospect_overall_status(prospect.id)

            return True, "Successfully saved new thread"

        # Check if message is from prospect
        if message.get("from_prospect") == True:
            # Update the Prospect's status to "ACTIVE CONVO"
            updated = update_prospect_email_outreach_status(
                prospect_email_id=prospect_email_id,
                new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
            )

            prospect: Prospect = Prospect.query.get(prospect_id)

            # Send Slack Notification if updated
            if updated:
                send_status_change_slack_block(
                    outreach_type=ProspectChannels.EMAIL,
                    prospect=prospect,
                    new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                    custom_message=" responded to your email! 🙌🏽",
                    metadata={}
                )

            # Calculate prospect overall status
            calculate_prospect_overall_status(prospect.id)

    return True, "Successfully saved new thread"


@celery.task(bind=True, max_retries=5)
def process_deltas_message_opened(self, deltas: Union[list[dict], dict]) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    This function processes `message.opened` deltas from the `message.opened` webhook.

    Args:
        deltas (Union[list[dict], dict]): A list of deltas from a Nylas webhook notification.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
     # Process deltas
    if type(deltas) == dict:
        process_single_message_opened.apply_async(
            args=[deltas]
        )
        return True, 1

    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_message_opened.apply_async(
            args=[delta]
        )

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_message_opened(self, delta: dict) -> tuple[bool, str]:
    """Process a single `message.opened` delta from a Nylas webhook notification.

    Args:
        delta (dict): A single `message.opened` delta from a Nylas webhook notification.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the delta was processed successfully, and a string containing the id of the message that was processed, or an error message.
    """
    delta_type = delta.get('type')
    if delta_type != 'message.opened':
        return False, "Delta type is not 'message.opened'"

    # Get object data
    object_data: dict = delta.get('object_data')
    if not object_data:
        return False, "No object_data in delta"

    # Get the ID of the connected email account and the client SDR
    account_id: str = object_data.get('account_id')
    if not account_id:
        return False, "No account ID in object data"
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.active == True,
        ClientSDR.nylas_account_id == account_id,
        ClientSDR.nylas_active == True,
    ).first()
    if not client_sdr:
        return False, "No client SDR found"

    # TODO: DELETE THIS - HARDCODE TO SELLSCALE FOR NOW
    if client_sdr.client_id != 1:
        return False, "Client is not SellScale"

    # The metadata should include a payload, which will include Prospect ID and Prospect Email ID
    metadata: dict = object_data.get('metadata')
    if not metadata:
        return False, "No metadata in delta"

    payload: dict = metadata.get('payload')
    if not payload:
        return False, "No payload in metadata"
    else:
        payload = json.loads(payload)

    prospect_id: int = payload.get('prospect_id')
    prospect_email_id: int = payload.get('prospect_email_id')
    client_sdr_id: int = payload.get('client_sdr_id')

    # Check that the information is correct:
    # 1. ClientSDR ID in payload matches ClientSDR ID in delta
    # 2. Prospect belongs to ClientSDR
    # 3. Prospect Email belongs to Prospect
    if client_sdr_id != client_sdr.id:
        return False, "Client SDR ID in payload does not match Client SDR ID in delta"
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return False, "No prospect found"
    if prospect.client_sdr_id != client_sdr.id:
        return False, "Prospect does not belong to Client SDR"
    if prospect.approved_prospect_email_id != prospect_email_id:
        return False, "Prospect Email does not belong to Prospect"

    # Update the Prospect's status to "OPENED"
    updated = update_prospect_email_outreach_status(
        prospect_email_id=prospect_email_id,
        new_status=ProspectEmailOutreachStatus.EMAIL_OPENED,
    )

    # Send Slack Message
    prospect: Prospect = Prospect.query.get(prospect_id)
    if updated:
        send_status_change_slack_block(
            outreach_type=ProspectChannels.EMAIL,
            prospect=prospect,
            new_status=ProspectEmailOutreachStatus.EMAIL_OPENED,
            custom_message=" opened your email! 📧",
            metadata={}
        )

    # Calculate prospect overall status
    calculate_prospect_overall_status(prospect_id)

    return True, "Successfully tracked email open"
