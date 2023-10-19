import json
from typing import Union
from app import db, celery
from src.automation.slack_notification import send_status_change_slack_block
from src.client.models import ClientSDR
from src.client.sdr.email.models import SDREmailBank
from src.client.sdr.email.services_email_bank import get_sdr_email_bank
from src.email_outbound.models import (
    EmailConversationMessage,
    EmailConversationThread,
    ProspectEmailOutreachStatus,
)
from src.email_outbound.services import update_prospect_email_outreach_status
from src.prospecting.models import Prospect, ProspectChannels
from src.prospecting.nylas.services import nylas_update_messages, nylas_update_threads
from src.prospecting.services import calculate_prospect_overall_status
from src.webhooks.models import NylasWebhookPayloads, NylasWebhookProcessingStatus


@celery.task(bind=True, max_retries=5)
def process_deltas_message_opened(
    self, deltas: Union[list[dict], dict], payload_id: int
) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    This function processes `message.opened` deltas from the `message.opened` webhook.

    Args:
        deltas (Union[list[dict], dict]): A list of deltas from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
    # Process deltas
    if type(deltas) == dict:
        process_single_message_opened.apply_async(args=[deltas, payload_id])
        return True, 1

    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_message_opened.apply_async(args=[delta, payload_id])

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_message_opened(
    self, delta: dict, payload_id: int
) -> tuple[bool, str]:
    """Process a single `message.opened` delta from a Nylas webhook notification.

    The system for updating an entire thread can be complex:
    1. Get the message ID from the delta
    2. Update the message
    3. Get the thread ID from the message
    4. Update the thread
    This situation can occur if we process a message.opened before a message.created, which is bound to happen.

    Args:
        delta (dict): A single `message.opened` delta from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the delta was processed successfully, and a string containing the id of the message that was processed, or an error message.
    """
    try:
        # Get payload and set it to "PROCESSING"
        nylas_payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(payload_id)
        if not nylas_payload:
            return False, "No payload found"
        nylas_payload.processing_status = NylasWebhookProcessingStatus.PROCESSING
        db.session.commit()

        delta = delta or nylas_payload.nylas_payload.get("deltas")[0]
        delta_type = delta.get("type")
        if delta_type != "message.opened":
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Delta type is not 'message.opened'"
            db.session.commit()
            return False, "Delta type is not 'message.opened'"

        # Get object data
        object_data: dict = delta.get("object_data")
        if not object_data:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No object_data in delta"
            db.session.commit()
            return False, "No object_data in delta"

        # Get the ID of the connected email account and the client SDR
        account_id: str = object_data.get("account_id")
        if not account_id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No account ID in object data"
            db.session.commit()
            return False, "No account ID in object data"

        # Get the SDR Email Bank in order to get the SDR
        email_bank: SDREmailBank = get_sdr_email_bank(
            nylas_account_id=account_id,
        )
        client_sdr: ClientSDR = ClientSDR.query.get(email_bank.client_sdr_id)
        if client_sdr and not client_sdr.active:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.INELIGIBLE
            nylas_payload.processing_fail_reason = "Client SDR is not active"
            db.session.commit()
            return False, "Client SDR is not active"
        if not client_sdr:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No client SDR found"
            db.session.commit()
            return False, "No client SDR found"

        # The metadata should include a payload, which will include Prospect ID and Prospect Email ID
        metadata: dict = object_data.get("metadata")
        if not metadata:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No metadata in delta"
            db.session.commit()
            return False, "No metadata in delta"

        # Get the payload so we can update the thread and messages
        # This will help us avoid race conditions
        payload: dict = metadata.get("payload")
        if not payload:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No payload in metadata"
            db.session.commit()
            return False, "No payload in metadata"
        else:
            payload = json.loads(payload)

        prospect_id: int = payload.get("prospect_id")
        prospect_email_id: int = payload.get("prospect_email_id")
        client_sdr_id: int = payload.get("client_sdr_id")

        # Update and get the thread
        success = nylas_update_threads(
            client_sdr_id=client_sdr.id, prospect_id=prospect_id, limit=5
        )
        if not success:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Failed to update thread"
            db.session.commit()
            return False, "Failed to update thread"

        # Get the id of the message, update and get the message
        message_id: str = metadata.get("message_id")
        success = nylas_update_messages(
            client_sdr_id=client_sdr.id,
            nylas_account_id=account_id,
            prospect_id=prospect_id,
            message_ids=[message_id],
        )
        if not success:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Failed to update messages"
            db.session.commit()
            return False, "Failed to update messages"
        convo_message: EmailConversationMessage = (
            EmailConversationMessage.query.filter_by(
                nylas_message_id=message_id
            ).first()
        )

        # Get the thread information
        if not convo_message:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No message found"
            db.session.commit()
            return False, "No message found"
        convo_thread: EmailConversationThread = EmailConversationThread.query.filter_by(
            nylas_thread_id=convo_message.nylas_thread_id
        ).first()
        if not convo_thread:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No conversation thread found"
            db.session.commit()
            return False, "No conversation thread found"

        # Update the messages based on thread ID.
        success = nylas_update_messages(
            client_sdr_id=client_sdr.id,
            nylas_account_id=account_id,
            prospect_id=prospect_id,
            thread_id=convo_thread.nylas_thread_id,
        )
        if not success:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = (
                "Failed to update all messages in the thread"
            )
            db.session.commit()
            return False, "Failed to update all messages in the thread"

        # Check that the information is correct:
        # 1. ClientSDR ID in payload matches ClientSDR ID in delta
        # 2. Prospect belongs to ClientSDR
        # 3. Prospect Email belongs to Prospect
        if client_sdr_id != client_sdr.id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = (
                "Client SDR ID in payload does not match Client SDR ID in delta"
            )
            db.session.commit()
            return (
                False,
                "Client SDR ID in payload does not match Client SDR ID in delta",
            )
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No prospect found"
            db.session.commit()
            return False, "No prospect found"
        if prospect.client_sdr_id != client_sdr.id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = (
                "Prospect does not belong to Client SDR"
            )
            db.session.commit()
            return False, "Prospect does not belong to Client SDR"
        if prospect.approved_prospect_email_id != prospect_email_id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = (
                "Prospect Email does not belong to Prospect"
            )
            db.session.commit()
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
                metadata={
                    "prospect_email": prospect.email,
                    "email_title": convo_thread.subject,
                },
            )

        # Calculate prospect overall status
        calculate_prospect_overall_status(prospect_id)

        nylas_payload.processing_status = NylasWebhookProcessingStatus.SUCCEEDED
        db.session.commit()
        return True, "Successfully tracked email open"
    except Exception as e:
        nylas_payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(payload_id)
        if not nylas_payload:
            return False, "No payload found"

        nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
        nylas_payload.processing_fail_reason = str(e)
        db.session.commit()
        return False, str(e)
