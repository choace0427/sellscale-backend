from app import db, celery
from typing import Union
from src.client.models import ClientSDR
from src.client.sdr.email.models import EmailType, SDREmailBank
from src.utils.slack import URL_MAP, send_slack_message

from src.webhooks.models import NylasWebhookPayloads, NylasWebhookProcessingStatus


@celery.task(bind=True, max_retries=5)
def process_deltas_account_invalid(
    self, deltas: Union[list[dict], dict], payload_id: int
) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    This function processes `account.invalid` deltas from the `account` webhook.

    Args:
        deltas (Union[list[dict], dict]): A list of deltas from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
    # Process deltas
    if type(deltas) == dict:
        process_single_account_invalid.apply_async(args=[deltas, payload_id])

    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_account_invalid.apply_async(args=[deltas, payload_id])

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_account_invalid(
    self, delta: dict, payload_id: int
) -> tuple[bool, str]:
    """Process a single `account.invalid` delta from a Nylas webhook notification.

    Args:
        delta (dict): A single `account.invalid` delta from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the delta was processed successfully, and a string containing the id of the account that was processed, or an error message.
    """
    try:
        # Get payload and set it to "PROCESSING"
        payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(
            payload_id)
        if not payload:
            return False, "No payload found"
        payload.processing_status = NylasWebhookProcessingStatus.PROCESSING
        db.session.commit()

        delta_type = delta.get("type")
        if delta_type != "account.invalid":
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "Delta type is not 'account.invalid'"
            db.session.commit()
            return False, "Delta type is not 'account.invalid'"

        # Get object data
        object_data: dict = delta.get("object_data")
        if not object_data:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED

        # Get account id
        account_id: str = object_data.get("account_id")

        # Get EmailBank entry
        email_bank: SDREmailBank = SDREmailBank.query.filter_by(
            nylas_connected_email_account_id=account_id).first()
        if not email_bank:
            payload.processing_status = NylasWebhookProcessingStatus.FAILED
            payload.processing_fail_reason = "No EmailBank entry found"
            db.session.commit()
            return False, "No EmailBank entry found"

        # Set EmailBank entry to inactive
        email_bank.nylas_active = False
        db.session.commit()

        # Send a Slack Notification to the SDR
        sdr: ClientSDR = ClientSDR.query.get(email_bank.client_sdr_id)
        email_address = email_bank.email_address
        reconnect_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=all/settings/emailConnection".format(
            auth_token=sdr.auth_token
        )

        webhook_urls = []
        webhook_urls.append(URL_MAP["csm-urgent-alerts"])
        # if email_bank.email_type != EmailType.SELLSCALE:    # If the email is not a SellScale email, send a notification to the SDR
        #     webhook_urls.append(sdr.pipeline_notifications_webhook_url)
        send_slack_message(
            message=f"URGENT: Your inbox '{email_address}' has been disconnected from SellScale. Services on this inbox will be significantly disrupted until reconnected",
            webhook_urls=webhook_urls,
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚨 ACTION NEEDED: INBOX DISCONNECTED 🚨",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Your email inbox has been disconnected from SellScale. Services on this inbox will be significantly disrupted until reconnected. Please reconnect using the link below."
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Inbox: `{email_address}`"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": " ",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Convo in Sight",
                            "emoji": True,
                        },
                        "value": reconnect_link,
                        "url": reconnect_link,
                        "action_id": "button-action",
                    },
                }
            ]
        )

        # Set payload to "SUCCEEDED"
        payload.processing_status = NylasWebhookProcessingStatus.SUCCEEDED
        db.session.commit()

        return True, account_id
    except Exception as e:
        nylas_payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(
            payload_id)
        if not nylas_payload:
            return False, "No payload found"

        nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
        nylas_payload.processing_fail_reason = str(e)
        db.session.commit()
        return False, str(e)
