from app import db, celery
from typing import Union
from src.automation.slack_notification import send_status_change_slack_block
from src.client.models import ClientSDR
from src.email_outbound.models import ProspectEmailOutreachStatus
from src.email_outbound.services import update_prospect_email_outreach_status
from src.prospecting.models import Prospect, ProspectChannels
from src.prospecting.nylas.nylas_wrappers import wrapped_nylas_get_single_thread
from src.prospecting.nylas.services import nylas_get_messages, nylas_update_threads
from src.prospecting.services import calculate_prospect_overall_status

from src.webhooks.models import NylasWebhookPayloads, NylasWebhookProcessingStatus
from src.webhooks.nylas.bounce_detection import is_email_bounced


@celery.task(bind=True, max_retries=5)
def process_deltas_message_created(
    self, deltas: Union[list[dict], dict], payload_id: int
) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    This function processes `message.created` deltas from the `message.created` webhook.

    Args:
        deltas (list[dict]): A list of deltas from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
    # Process deltas
    if type(deltas) == dict:
        process_single_message_created.apply_async(args=[deltas, payload_id])
        return True, 1

    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_message_created.apply_async(args=[delta, payload_id])

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_message_created(
    self, delta: dict, payload_id: int
) -> tuple[bool, str]:
    """Process a single `message.created` delta from a Nylas webhook notification.

    Args:
        delta (dict): A single `message.created` delta from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the delta was processed successfully, and a string containing the id of the message that was processed, or an error message.
    """
    try:
        # Get payload and set it to "PROCESSING"
        payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(payload_id)
        if not payload:
            return False, "No payload found"
        payload.processing_status = NylasWebhookProcessingStatus.PROCESSING
        db.session.commit()

        delta_type = delta.get("type")
        if delta_type != "message.created":
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "Delta type is not 'message.created'"
            db.session.commit()
            return False, "Delta type is not 'message.created'"

        # Get object data
        object_data: dict = delta.get("object_data")
        if not object_data:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "No object_data in delta"
            db.session.commit()
            return False, "No object_data in delta"

        # Get the ID of the connected email account and the client SDR
        account_id: str = object_data.get("account_id")
        if not account_id:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "No account ID in object data"
            db.session.commit()
            return False, "No account ID in object data"
        client_sdr: ClientSDR = ClientSDR.query.filter(
            ClientSDR.nylas_account_id == account_id,
            ClientSDR.nylas_active == True,
        ).first()
        if client_sdr and not client_sdr.active:
            payload.processing_status = NylasWebhookProcessingStatus.INELIGIBLE
            payload.processing_fail_reason = "Client SDR is not active"
            db.session.commit()
            return False, "Client SDR is not active"
        if not client_sdr:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "No client SDR found"
            db.session.commit()
            return False, "No client SDR found"

        # Get thread ID - the ID of the thread that the message belongs to
        attributes: dict = object_data.get("attributes")
        if not attributes:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "No attributes in object data"
            db.session.commit()
            return False, "No attributes in object data"
        thread_id: str = attributes.get("thread_id")
        if not thread_id:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "No thread ID"
            db.session.commit()
            return False, "No thread ID"

        # Get information about the thread
        thread: dict = wrapped_nylas_get_single_thread(
            client_sdr.nylas_auth_code, thread_id
        )

        # Check if participants include a prospect.
        # We only save threads with prospects.
        participants: list[dict] = thread.get("participants")
        if not participants:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "No participants in thread"
            db.session.commit()
            return False, "No participants in thread"
        participants = [participant.get("email") for participant in participants]

        prospect: Prospect = Prospect.query.filter(
            Prospect.client_id == client_sdr.client_id,
            Prospect.client_sdr_id == client_sdr.id,
            Prospect.email.in_(participants),
        ).first()
        if not prospect:
            payload.processing_status = NylasWebhookProcessingStatus.INELIGIBLE
            payload.processing_fail_reason = "No prospect found"
            db.session.commit()
            return False, "No prospect found"
        prospect_email_id = prospect.approved_prospect_email_id
        prospect_id = prospect.id

        # Prospect was found, so we should save the thread and messages.
        result = nylas_update_threads(client_sdr.id, prospect.id, 5)
        if not result:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "Failed to save thread"
            db.session.commit()
            return False, "Failed to save thread"

        messages: list[dict] = nylas_get_messages(
            client_sdr_id=client_sdr.id,
            prospect_id=prospect.id,
            nylas_account_id=account_id,
            thread_id=thread.get("id"),
        )
        for message in messages:
            # Check if message is bounced
            email_from: list = message.get("message_from", [{"email": None}])
            if len(email_from) == 1:
                email_from: str = email_from[0].get("email")
                bounced = is_email_bounced(email_from, message.get("body"))
                if bounced:
                    # Update the Prospect's status to "BOUNCED"
                    updated = update_prospect_email_outreach_status(
                        prospect_email_id=prospect_email_id,
                        new_status=ProspectEmailOutreachStatus.BOUNCED,
                    )

                    # Calculate prospect overall status
                    calculate_prospect_overall_status(prospect.id)

                    payload.processing_status = NylasWebhookProcessingStatus.SUCCEEDED
                    db.session.commit()
                    return True, "Successfully saved new thread - Email was BOUNCED"

            # Check if message is from prospect
            if message.get("from_prospect") == True:
                # Update the Prospect's status to "ACTIVE CONVO"
                updated = update_prospect_email_outreach_status(
                    prospect_email_id=prospect_email_id,
                    new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                )

                prospect: Prospect = Prospect.query.get(prospect_id)

                # Send Slack Notification if updated
                # DEPRECATED: Redundant because thread_replied should be a better / more reliable hook
                # if updated:
                #     send_status_change_slack_block(
                #         outreach_type=ProspectChannels.EMAIL,
                #         prospect=prospect,
                #         new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                #         custom_message=" responded to your email! 🙌🏽",
                #         metadata={},
                #         last_email_message=message.get("snippet"),
                #     )

                # Calculate prospect overall status
                calculate_prospect_overall_status(prospect.id)

        payload.processing_status = NylasWebhookProcessingStatus.SUCCEEDED
        db.session.commit()
        return True, "Successfully saved new thread"
    except Exception as e:
        payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(payload_id)
        if not payload:
            return False, "No payload found"

        payload.processing_status = NylasWebhookProcessingStatus.FAILED
        payload.processing_fail_reason = str(e)
        db.session.commit()
        return False, str(e)
