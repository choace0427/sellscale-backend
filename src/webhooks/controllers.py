from flask import Blueprint, jsonify, request
from src.webhooks.models import NylasWebhookProcessingStatus, NylasWebhookType
from src.webhooks.nylas.services import (
    create_nylas_webhook_payload_entry,
    process_deltas_message_created,
    process_deltas_message_opened,
    process_deltas_event_update,
)
from app import app, db

import hmac
import hashlib
import os

WEBHOOKS_BLUEPRINT = Blueprint('webhooks', __name__)

NYLAS_CLIENT_SECRET = os.environ.get("NYLAS_CLIENT_SECRET")

def verify_signature(message, key, signature):
    """
    This function will verify the authenticity of a digital signature.
    For security purposes, Nylas includes a digital signature in the headers
    of every webhook notification, so that clients can verify that the
    webhook request came from Nylas and no one else. The signing key
    is your OAuth client secret, which only you and Nylas know.
    """
    digest = hmac.new(key, msg=message, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


@WEBHOOKS_BLUEPRINT.route('/nylas/message_created', methods=['GET', 'POST'])
def nylas_webhook_message_created():
    """Webhook for Nylas message created event."""

    # When you first tell Nylas about your webhook, it will test that webhook
    # URL with a GET request to make sure that it responds correctly.
    # We just need to return the `challenge` parameter to indicate that this
    # is a valid webhook URL.
    if request.method == 'GET' and "challenge" in request.args:
        return request.args["challenge"]

    # Alright, this is a POST request, which means it's a webhook notification.
    # The question is, is it genuine or fake? Check the signature to find out.
    is_genuine = verify_signature(
        message=request.data,
        key=NYLAS_CLIENT_SECRET.encode("utf8"),
        signature=request.headers.get("X-Nylas-Signature"),
    )
    if not is_genuine:
        return "Signature verification failed!", 401

    # Let's save the webhook notification to our database, so that we can
    # process it later.
    data = request.get_json()
    payload_id = create_nylas_webhook_payload_entry(
        nylas_payload=data,
        nylas_webhook_type=NylasWebhookType.MESSAGE_CREATED,
        processing_status=NylasWebhookProcessingStatus.PENDING,
        processing_fail_reason=None
    )

    # Alright, we have a genuine webhook notification from Nylas!
    # Let's find out what it says...
    for delta in data["deltas"]:
        # Processing the data might take awhile, or it might fail.
        # As a result, instead of processing it right now, we'll push a task
        # onto the Celery task queue, to handle it later. That way,
        # we've got the data saved, and we can return a response to the
        # Nylas webhook notification right now.
        process_deltas_message_created.apply_async(
            args=[delta]
        )

    # Now that all the `process_delta` tasks have been queued, we can
    # return an HTTP response to Nylas, to let them know that we processed
    # the webhook notification successfully.
    return "Deltas for `message.created` have been queued", 200


@WEBHOOKS_BLUEPRINT.route('/nylas/message_opened', methods=['GET', 'POST'])
def nylas_webhook_message_opened():
    """Webhook for Nylas message opened event."""

    if request.method == 'GET' and "challenge" in request.args:
        return request.args["challenge"]

    is_genuine = verify_signature(
        message=request.data,
        key=NYLAS_CLIENT_SECRET.encode("utf8"),
        signature=request.headers.get("X-Nylas-Signature"),
    )
    if not is_genuine:
        return "Signature verification failed!", 401

    # Let's save the webhook notification to our database, so that we can
    # process it later.
    data = request.get_json()
    payload_id = create_nylas_webhook_payload_entry(
        nylas_payload=data,
        nylas_webhook_type=NylasWebhookType.MESSAGE_OPENED,
        processing_status=NylasWebhookProcessingStatus.PENDING,
        processing_fail_reason=None
    )

    data = request.get_json()
    deltas = data["deltas"]

    process_deltas_message_opened.apply_async(
        args=[deltas]
    )

    return "Deltas for `message.opened` have been queued", 200


@WEBHOOKS_BLUEPRINT.route('/nylas/event_update', methods=['GET', 'POST'])
def nylas_webhook_event_update():
    """Webhook for Nylas event update."""

    if request.method == 'GET' and "challenge" in request.args:
        return request.args["challenge"]

    is_genuine = verify_signature(
        message=request.data,
        key=NYLAS_CLIENT_SECRET.encode("utf8"),
        signature=request.headers.get("X-Nylas-Signature"),
    )
    if not is_genuine:
        return "Signature verification failed!", 401

    # Let's save the webhook notification to our database, so that we can
    # process it later.
    data = request.get_json()
    deltas = data["deltas"]
    if deltas[0]["type"] == "event.created":
        webhook_type = NylasWebhookType.EVENT_CREATED
    elif deltas[0]["type"] == "event.updated":
        webhook_type = NylasWebhookType.EVENT_UPDATED
    else:
        raise Exception("Invalid webhook type")
    payload_id = create_nylas_webhook_payload_entry(
        nylas_payload=data,
        nylas_webhook_type=webhook_type,
        processing_status=NylasWebhookProcessingStatus.PENDING,
        processing_fail_reason=None
    )

    process_deltas_event_update.apply_async(
        args=[deltas]
    )

    return "Deltas for `event.created` or `event.updated` have been queued", 200
