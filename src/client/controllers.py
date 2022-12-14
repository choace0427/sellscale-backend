from flask import Blueprint, request, jsonify
from src.client.models import ClientArchetype
from src.client.services import (
    create_client,
    create_client_archetype,
    create_client_sdr,
    rename_archetype,
    toggle_archetype_active,
    update_client_sdr_email,
    update_client_sdr_scheduling_link,
    update_client_pipeline_notification_webhook,
    update_client_sdr_pipeline_notification_webhook,
    test_client_pipeline_notification_webhook,
    test_client_sdr_pipeline_notification_webhook,
    send_stytch_magic_link,
    approve_stytch_client_sdr_token,
    verify_client_sdr_auth_token,
)

from src.utils.request_helpers import get_request_parameter

CLIENT_BLUEPRINT = Blueprint("client", __name__)


@CLIENT_BLUEPRINT.route("/")
def index():
    return "OK", 200


@CLIENT_BLUEPRINT.route("/", methods=["POST"])
def create():
    company = get_request_parameter("company", request, json=True, required=True)
    contact_name = get_request_parameter(
        "contact_name", request, json=True, required=True
    )
    contact_email = get_request_parameter(
        "contact_email", request, json=True, required=True
    )

    linkedin_outbound_enabled = get_request_parameter(
        "linkedin_outbound_enabled", request, json=True, required=True
    )
    email_outbound_enabled = get_request_parameter(
        "email_outbound_enabled", request, json=True, required=True
    )

    resp = create_client(
        company=company, contact_name=contact_name, contact_email=contact_email, linkedin_outbound_enabled=linkedin_outbound_enabled, email_outbound_enabled=email_outbound_enabled
    )

    return jsonify(resp)


@CLIENT_BLUEPRINT.route("/archetype", methods=["POST"])
def create_archetype():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    archetype = get_request_parameter("archetype", request, json=True, required=True)
    filters = get_request_parameter("filters", request, json=True, required=False)
    disable_ai_after_prospect_engaged = get_request_parameter(
        "disable_ai_after_prospect_engaged", request, json=True, required=True
    )
    base_archetype_id = get_request_parameter(
        "base_archetype_id", request, json=True, required=False
    )
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )

    ca: object = create_client_archetype(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        archetype=archetype,
        filters=filters,
        base_archetype_id=base_archetype_id,
        disable_ai_after_prospect_engaged=disable_ai_after_prospect_engaged,
    )
    if not ca:
        return "Client not found", 404

    return ca


@CLIENT_BLUEPRINT.route("/sdr", methods=["POST"])
def create_sdr():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    name = get_request_parameter("name", request, json=True, required=True)
    email = get_request_parameter("email", request, json=True, required=True)

    resp = create_client_sdr(client_id=client_id, name=name, email=email)
    if not resp:
        return "Client not found", 404

    return resp


@CLIENT_BLUEPRINT.route("/reset_client_sdr_auth_token", methods=["POST"])
def reset_client_sdr_auth_token():
    from src.client.services import reset_client_sdr_sight_auth_token

    sdr_id = get_request_parameter("client_sdr_id", request, json=True, required=True)

    resp = reset_client_sdr_sight_auth_token(client_sdr_id=sdr_id)
    if not resp:
        return "Client not found", 404

    return jsonify(resp)


@CLIENT_BLUEPRINT.route("/archetype", methods=["PATCH"])
def update_archetype_name():
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    new_name = get_request_parameter("new_name", request, json=True, required=True)

    success = rename_archetype(
        client_archetype_id=client_archetype_id, new_name=new_name
    )

    if not success:
        return "Failed to update name", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/archetype/toggle_active", methods=["PATCH"])
def patch_toggle_archetype_active():
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )

    success = toggle_archetype_active(archetype_id=client_archetype_id)

    if not success:
        return "Failed to update active", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/update_scheduling_link", methods=["PATCH"])
def patch_update_scheduling_link():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    scheduling_link = get_request_parameter(
        "scheduling_link", request, json=True, required=True
    )

    success = update_client_sdr_scheduling_link(
        client_sdr_id=client_sdr_id, scheduling_link=scheduling_link
    )

    if not success:
        return "Failed to update scheduling link", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/update_email", methods=["PATCH"])
def patch_update_sdr_email():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    email = get_request_parameter("email", request, json=True, required=True)

    success = update_client_sdr_email(client_sdr_id=client_sdr_id, email=email)

    if not success:
        return "Failed to update email", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/update_pipeline_webhook", methods=["PATCH"])
def patch_update_pipeline_webhook():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    webhook = get_request_parameter("webhook", request, json=True, required=True)

    success = update_client_pipeline_notification_webhook(
        client_id=client_id, webhook=webhook
    )

    if not success:
        return "Failed to update pipeline webhook", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/test_webhook", methods=["POST"])
def post_test_webhook():
    client_id = get_request_parameter("client_id", request, json=True, required=True)

    success = test_client_pipeline_notification_webhook(client_id=client_id)

    if not success:
        return "Failed to test pipeline webhook", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/update_pipeline_client_sdr_webhook", methods=["PATCH"])
def patch_update_pipeline_client_sdr_webhook():
    """Update the Client SDR Webhook

    Returns:
        response.status_code: 200 if successful, 404 if not
    """
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    webhook = get_request_parameter("webhook", request, json=True, required=True)

    success = update_client_sdr_pipeline_notification_webhook(
        client_sdr_id=client_sdr_id, webhook=webhook
    )

    if not success:
        return "Failed to update pipeline client sdr webhook", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/test_sdr_webhook", methods=["POST"])
def post_test_sdr_webhook():
    """Sends a test message through the Client SDR Webhook

    Returns:
        response.status_code: 200 if successful, 404 if not
    """
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )

    success = test_client_sdr_pipeline_notification_webhook(client_sdr_id=client_sdr_id)

    if not success:
        return "Failed to test pipeline client sdr webhook", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/send_magic_link_login", methods=["POST"])
def post_send_magic_link_login():
    client_sdr_email: str = get_request_parameter(
        "client_sdr_email", request, json=True, required=True
    )
    success = send_stytch_magic_link(
        client_sdr_email=client_sdr_email,
    )
    if not success:
        return (
            "Failed to send magic link. Please ensure this is a valid SellScale account email.",
            404,
        )
    return (
        "Magic login link sent to {}. Please check your inbox.".format(
            client_sdr_email
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/approve_auth_token", methods=["POST"])
def post_approve_auth_token():
    client_sdr_email: str = get_request_parameter(
        "client_sdr_email", request, json=True, required=True
    )
    token = get_request_parameter("token", request, json=True, required=True)
    token_payload = approve_stytch_client_sdr_token(
        client_sdr_email=client_sdr_email, token=token
    )
    return jsonify(token_payload)


@CLIENT_BLUEPRINT.route("/verify_client_sdr_auth_token", methods=["POST"])
def post_verify_client_sdr_auth_token():
    auth_token = get_request_parameter("auth_token", request, json=True, required=True)
    success = verify_client_sdr_auth_token(
        auth_token=auth_token,
    )
    if not success:
        return "Failed to verify auth token", 404
    return "OK", 200
