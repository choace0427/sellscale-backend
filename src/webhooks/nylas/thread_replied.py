from datetime import datetime
import json
from typing import Union
from app import db, celery
from src.automation.slack_notification import send_status_change_slack_block
from src.client.models import ClientSDR
from src.client.sdr.email.models import SDREmailBank
from src.client.sdr.email.services_email_bank import email_belongs_to_sdr, get_sdr_email_bank
from src.email_outbound.models import EmailConversationMessage, EmailConversationThread, ProspectEmailOutreachStatus
from src.email_outbound.services import update_prospect_email_outreach_status
from src.email_scheduling.models import EmailMessagingSchedule
from src.prospecting.models import Prospect, ProspectChannels
from src.prospecting.nylas.services import nylas_update_messages, nylas_update_threads
from src.prospecting.services import calculate_prospect_overall_status
from src.webhooks.models import NylasWebhookPayloads, NylasWebhookProcessingStatus

@celery.task(bind=True, max_retries=5)
def process_deltas_thread_replied(
    self, deltas: Union[list[dict], dict], payload_id: int
) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    This function processes `thread.replied` deltas from the `thread.replied` webhook.

    Args:
        deltas (Union[list[dict], dict]): A list of deltas from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
    # Process deltas
    if type(deltas) == dict:
        process_single_thread_replied.apply_async(args=[deltas, payload_id])
        return True, 1

    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_thread_replied.apply_async(args=[delta, payload_id])

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_thread_replied(
    self, delta: dict, payload_id: int
) -> tuple[bool, str]:
    """Process a single `thread.replied` delta from a Nylas webhook notification.

    Args:
        delta (dict): A single `thread.replied` delta from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the delta was processed successfully, and a string containing the id of the message that was processed, or an error message.
    """
    try:
        # Get payload and set it to "PROCESSING"
        nylas_payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(
            payload_id)
        if not nylas_payload:
            return False, "No payload found"
        nylas_payload.processing_status = NylasWebhookProcessingStatus.PROCESSING
        db.session.commit()

        delta_type = delta.get("type")
        if delta_type != "thread.replied":
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Delta type is not 'thread.replied'"
            db.session.commit()
            return False, "Delta type is not 'thread.replied'"

        # Get object data
        object_data: dict = delta.get("object_data")
        if not object_data:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No object_data found"
            db.session.commit()
            return False, "No object_data found"

        # Get the ID of the connected email account and the Client SDR
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

        # Get the payload
        payload: dict = metadata.get("payload")
        if not payload:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No payload in metadata"
            db.session.commit()
            return False, "No payload in metadata"
        else:
            payload = json.loads(payload)

        # Parse the payload
        prospect_id: int = payload.get("prospect_id")
        prospect_email_id: int = payload.get("prospect_email_id")
        client_sdr_id: int = payload.get("client_sdr_id")

        # Check that the information is correct:
        # 1. ClientSDR ID in payload matches ClientSDR ID in delta
        # 2. Prospect belongs to ClientSDR
        # 3. Prospect Email belongs to Prospect
        if client_sdr_id != client_sdr.id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Client SDR ID in payload does not match Client SDR ID in delta"
            db.session.commit()
            return False, "Client SDR ID in payload does not match Client SDR ID in delta"
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No prospect found"
            db.session.commit()
            return False, "No prospect found"
        if prospect.client_sdr_id != client_sdr.id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Prospect does not belong to Client SDR"
            db.session.commit()
            return False, "Prospect does not belong to Client SDR"
        if prospect.approved_prospect_email_id != prospect_email_id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Prospect Email does not belong to Prospect"
            db.session.commit()
            return False, "Prospect Email does not belong to Prospect"

        # Get thread ID - the ID of the thread that the message belongs to
        thread_id: str = metadata.get("thread_id")
        if not thread_id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No thread ID"
            db.session.commit()
            return False, "No thread ID"

        # Update the thread
        success = nylas_update_threads(client_sdr_id, prospect_id, 5)
        if not success:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Failed to update thread"
            db.session.commit()
            return False, "Failed to update thread"

        # Update the messages in this thread
        success = nylas_update_messages(
            client_sdr_id=client_sdr_id,
            nylas_account_id=account_id,
            prospect_id=prospect_id,
            thread_id=thread_id
        )
        if not success:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Failed to update messages"
            db.session.commit()
            return False, "Failed to update messages"

        # Check if this message is from me. If not, then a prospect must have replied. Mark the thread as prospect_replied.
        from_self: bool = metadata.get("from_self")
        email_bank: SDREmailBank = get_sdr_email_bank(
            nylas_account_id=account_id
        )
        from_sdr: bool = email_belongs_to_sdr(client_sdr_id, email_bank.email_address)
        if not from_sdr:
            thread: EmailConversationThread = EmailConversationThread.query.filter_by(
                nylas_thread_id=thread_id
            )
            if not thread:
                nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
                nylas_payload.processing_fail_reason = "No thread found"
                db.session.commit()
                return False, "No thread found"
            thread.prospect_replied = True

            # Update the Prospect's status to "ACTIVE_CONVO"
            updated = update_prospect_email_outreach_status(
                prospect_email_id=prospect_email_id,
                new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
            )

            # Send Slack Message
            if updated:
                # Get the latest message and update the prospect accordingly
                latest_message: EmailConversationMessage = EmailConversationMessage.query.filter_by(
                    prospect_id=prospect_id
                ).order_by(EmailConversationMessage.date_received.desc()).first()

                message_from = latest_message.message_from[0].get('email')
                message_subject = latest_message.subject
                message_snippet = latest_message.snippet

                send_status_change_slack_block(
                    outreach_type=ProspectChannels.EMAIL,
                    prospect=prospect,
                    new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                    custom_message=" responded to your email! 🙌🏽",
                    metadata={
                        "prospect_email": message_from,
                        "email_title": message_subject,
                        "email_snippet": message_snippet,
                    },
                )

            # Block future AI emails
            now = datetime.utcnow()
            future_messages: list[EmailMessagingSchedule] = EmailMessagingSchedule.query.filter(
                EmailMessagingSchedule.prospect_email_id == prospect_email_id,
                EmailMessagingSchedule.date_scheduled > now
            ).all()
            for message in future_messages:
                # Delete the message
                db.session.delete(message)
            db.session.commit()

            # Calculate prospect overall status
            calculate_prospect_overall_status(prospect_id)

        nylas_payload.processing_status = NylasWebhookProcessingStatus.SUCCEEDED
        db.session.commit()
        return True, "Successfully tracked thread replied"
    except Exception as e:
        nylas_payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(
            payload_id)
        if not nylas_payload:
            return False, "No payload found"

        nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
        nylas_payload.processing_fail_reason = str(e)
        db.session.commit()
        return False, str(e)
