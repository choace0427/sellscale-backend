from app import db, celery
from src.client.models import ClientSDR
from src.prospecting.models import Prospect

from src.prospecting.nylas.services import nylas_update_threads
from src.prospecting.nylas.nylas_wrappers import wrapped_nylas_get_single_thread


@celery.task(bind=True, max_retries=5)
def process_deltas_message_created(deltas: list[dict]) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    This function processes `message.created` deltas from the `message.created` webhook.

    Args:
        deltas (list[dict]): A list of deltas from a Nylas webhook notification.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
    # Process deltas
    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_message_created.apply_async(
            args=[delta]
        )

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_message_created(delta: dict) -> tuple[bool, str]:
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
    )
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

    # Prospect was found, so we should save the thread and messages.
    result = nylas_update_threads(client_sdr.id, prospect.id, 5)
    if not result:
        return False, "Failed to save thread"

    # TODO: Get the messages and determine if any of them were from the prospect.

    return True, "Successfully saved new thread"