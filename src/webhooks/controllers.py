import json

from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message, URL_MAP
from src.webhooks.models import NylasWebhookProcessingStatus, NylasWebhookType
from src.webhooks.nylas.account_invalid import process_deltas_account_invalid
from src.webhooks.nylas.event_update import process_deltas_event_update
from src.webhooks.nylas.message_created import process_deltas_message_created
from src.webhooks.nylas.message_opened import process_deltas_message_opened
from src.webhooks.nylas.services import (
    create_nylas_webhook_payload_entry,
)
from app import app, db

import hmac
import hashlib
import os

from src.webhooks.nylas.thread_replied import process_deltas_thread_replied

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
            args=[delta, payload_id]
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
        args=[deltas, payload_id]
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
        args=[deltas, payload_id]
    )

    return "Deltas for `event.created` or `event.updated` have been queued", 200


@WEBHOOKS_BLUEPRINT.route('/nylas/thread_replied', methods=['GET', 'POST'])
def nylas_webhook_thread_replied():
    """Webhook for Nylas thread replied event."""

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
        nylas_webhook_type=NylasWebhookType.THREAD_REPLIED,
        processing_status=NylasWebhookProcessingStatus.PENDING,
        processing_fail_reason=None
    )

    data = request.get_json()
    deltas = data["deltas"]

    process_deltas_thread_replied.apply_async(
        args=[deltas, payload_id]
    )

    return "Deltas for `thread.replied` have been queued", 200


@WEBHOOKS_BLUEPRINT.route('/nylas/account_invalid', methods=['GET', 'POST'])
def nylas_webhook_account_invalid():
    """Webhook for Nylas account event."""

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
        nylas_webhook_type=NylasWebhookType.ACCOUNT_INVALID,
        processing_status=NylasWebhookProcessingStatus.PENDING,
        processing_fail_reason=None
    )

    # Alright, we have a genuine webhook notification from Nylas
    # Let's find out what it says...
    deltas = data["deltas"]

    process_deltas_account_invalid.apply_async(
        args=[deltas, payload_id]
    )

    return "Deltas for `account.invalid` have been queued", 200


@WEBHOOKS_BLUEPRINT.route("/get_client_webhooks", methods=["GET"])
@require_user
def get_client_webhooks(client_sdr_id: int):
    """Get all the webhooks for a client."""
    from src.client.models import ClientSDR, Client

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    webhooks = {"on_demo_set": client.on_demo_set_webhook}

    return jsonify(webhooks), 200


@WEBHOOKS_BLUEPRINT.route("/set_on_demo_set_webhook", methods=["POST"])
@require_user
def set_on_demo_set_webhook(client_sdr_id: int):
    """Set the webhook for when a demo is set."""
    from src.client.models import ClientSDR, Client

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    on_demo_set_webhook = get_request_parameter(
        key="on_demo_set_webhook", req=request, required=True, json=True
    )

    client.on_demo_set_webhook = on_demo_set_webhook
    db.session.commit()

    return "Webhook set successfully", 200


@WEBHOOKS_BLUEPRINT.route("/prospect/find-phone-number/<client_sdr_id>/<prospect_id>", methods=["POST"])
def apollo_set_number_webhook(client_sdr_id: int, prospect_id: int):
    from src.prospecting.models import Prospect
    prospect = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.id == prospect_id,
    ).first()

    if not prospect:
        return

    data = request.json

    send_slack_message(
        message=f"Find phone number webhook called: {json.dumps(data)}",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    if not data:
        return

    if not data.get("person") or not data.get("person").get("contact") or not data.get("person").get("contact").get("phone_numbers"):
        prospect.reveal_phone_number = True

        db.session.add(prospect)
        db.session.commit()

        return "Webhook set successfully", 400

    phone_numbers = data["person"]["contact"]["phone_numbers"]

    # For now only supporting mobile number
    for phone_number in phone_numbers:
        if phone_number["type"] == "mobile":
            prospect.phone_number = phone_number["sanitized_number"]
            prospect.reveal_phone_number = True

            db.session.add(prospect)
            db.session.commit()

            return "Webhook set successfully", 200

    # If we get here, we did not find the phone number successfully

    prospect.reveal_phone_number = True
    prospect.phone_number = None
    db.session.add(prospect)
    db.session.commit()

    return "Webhook set successfully", 400
