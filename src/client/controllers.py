from flask import Blueprint, request, jsonify
from src.client.models import ClientArchetype
from src.message_generation.models import GeneratedMessageCTA
from src.client.services import (
    create_client,
    create_client_archetype,
    create_client_sdr,
    get_sdr_available_outbound_channels,
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
    update_client_sdr_manual_warning_message,
    update_client_sdr_weekly_li_outbound_target,
    update_client_sdr_weekly_email_outbound_target,
    get_ctas,
    get_client_archetypes,
    get_cta_by_archetype_id,
    get_client_sdr,
    get_prospect_upload_stats_by_upload_id,
    get_prospect_upload_details_by_upload_id,
    get_transformers_by_archetype_id,
    get_all_uploads_by_archetype_id,
    toggle_client_sdr_autopilot_enabled,
)
from src.client.services_client_archetype import (
    update_transformer_blocklist,
    replicate_transformer_blocklist,
)
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.client.models import ClientSDR, Client

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
        company=company,
        contact_name=contact_name,
        contact_email=contact_email,
        linkedin_outbound_enabled=linkedin_outbound_enabled,
        email_outbound_enabled=email_outbound_enabled,
    )

    return jsonify(resp)



@CLIENT_BLUEPRINT.route("/archetype", methods=["POST"])
@require_user
def create_archetype(client_sdr_id: int):
    archetype = get_request_parameter("archetype", request, json=True, required=True)
    filters = get_request_parameter("filters", request, json=True, required=False)
    disable_ai_after_prospect_engaged = get_request_parameter(
        "disable_ai_after_prospect_engaged", request, json=True, required=True
    )
    base_archetype_id = get_request_parameter(
        "base_archetype_id", request, json=True, required=False
    )

    # Get client ID from client SDR ID.
    client_sdr = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    if not client_sdr or not client_sdr.client_id:
        return "Failed to find client ID from auth token", 500

    ca: object = create_client_archetype(
        client_id=client_sdr.client_id,
        client_sdr_id=client_sdr_id,
        archetype=archetype,
        filters=filters,
        base_archetype_id=base_archetype_id,
        disable_ai_after_prospect_engaged=disable_ai_after_prospect_engaged,
    )
    if not ca:
        return "Client not found", 404

    return ca


@CLIENT_BLUEPRINT.route("/archetype/get_archetypes", methods=["GET"])
@require_user
def get_archetypes(client_sdr_id: int):
    """Gets all the archetypes for a client SDR, with option to search filter by archetype name"""
    query = (
        get_request_parameter(
            "query", request, json=False, required=False, parameter_type=str
        )
        or ""
    )

    archetypes = get_client_archetypes(client_sdr_id=client_sdr_id, query=query)
    return jsonify({"message": "Success", "archetypes": archetypes}), 200


@CLIENT_BLUEPRINT.route("/sdr", methods=["GET"])
@require_user
def get_sdr(client_sdr_id: int):
    """Gets the client SDR"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    sdr_dict = client_sdr.to_dict()

    if client_sdr:
        client: Client = Client.query.get(client_sdr.client_id)
        sdr_dict = sdr_dict | {"client": client.to_dict()}

    return jsonify({"message": "Success", "sdr_info": sdr_dict}), 200


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


@CLIENT_BLUEPRINT.route("/prospect_upload/<upload_id>/stats", methods=["GET"])
@require_user
def get_prospect_upload_stats(client_sdr_id: int, upload_id: int):
    """Gets basic stats of a prospect upload"""

    result = get_prospect_upload_stats_by_upload_id(client_sdr_id, upload_id)

    return jsonify(result), result.get('status_code')


@CLIENT_BLUEPRINT.route("/prospect_upload/<upload_id>/details", methods=["GET"])
@require_user
def get_prospect_upload_details(client_sdr_id: int, upload_id: int):
    """Gets prospect details of a prospect upload"""

    result = get_prospect_upload_details_by_upload_id(client_sdr_id, upload_id)

    return jsonify(result), result.get('status_code')


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


@CLIENT_BLUEPRINT.route("/sdr/get_available_outbound_channels", methods=["GET"])
@require_user
def get_sdr_available_outbound_channels_endpoint(client_sdr_id: int):
    """Gets all the available outbound channels for a Client SDR.

    Uses "Psuedo-permissions" based off of SDR SLAs.

    Returns a dictionary of the form:
    {
        "outbound_channel_type": {
            "name": "Outbound Channel Name",
            "description": "Outbound Channel Description",
            "statuses_available": ["channel_type_status_1", ...],
            "channel_type_status_1": {
                "name": "channel_type_status_1_human_readable",
                "description": "channel_type_status_1 description",
                "enum_val": "channel_type_status_1",
                "sellscale_enum_val": "channel_type_status_1_sellscale_enum_val",
            },
            ...
        }
    }

    Example:
    {
        "EMAIL": {
            "name": "Email",
            "description": "Email outbound",
            "statuses_available": ["ACTIVE_CONVO", ...],
            "ACTIVE_CONVO": {
                "name": "Active Conversation",
                "description": "There is an active conversation between Prospect and SDR",
                "enum_val": "ACTIVE_CONVO",
                "sellscale_enum_val": "ACTIVE_CONVO",
            }
            ...
        }
    }
    """
    available_outbound_channels = get_sdr_available_outbound_channels(
        client_sdr_id=client_sdr_id
    )
    return (
        jsonify(
            {
                "message": "Success",
                "available_outbound_channels": available_outbound_channels,
            }
        ),
        200,
    )


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
            jsonify(
                {
                    "message": "Failed to send magic link. Please ensure this is a valid SellScale account email."
                }
            ),
            401,
        )
    return (
        jsonify(
            {
                "message": "Magic login link sent to {}. Please check your inbox.".format(
                    client_sdr_email
                )
            }
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
    return token_payload


@CLIENT_BLUEPRINT.route("/verify_client_sdr_auth_token", methods=["POST"])
def post_verify_client_sdr_auth_token():
    auth_token = get_request_parameter("auth_token", request, json=True, required=True)
    success = verify_client_sdr_auth_token(
        auth_token=auth_token,
    )
    if not success:
        return jsonify({"message": "Failed to verify auth token"}), 401
    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/update_sdr_manual_warning_message", methods=["POST"])
def post_update_sdr_manual_warning_message():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    manual_warning_message: str = get_request_parameter(
        "manual_warning_message", request, json=True, required=True
    )
    success = update_client_sdr_manual_warning_message(
        client_sdr_id=client_sdr_id, manual_warning=manual_warning_message
    )
    if not success:
        return "Failed to update manual warning message", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/update_weekly_li_outbound_target", methods=["PATCH"])
def patch_update_sdr_weekly_li_outbound_target():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    weekly_li_outbound_target: int = get_request_parameter(
        "weekly_li_outbound_target", request, json=True, required=True
    )
    success = update_client_sdr_weekly_li_outbound_target(
        client_sdr_id=client_sdr_id, weekly_li_outbound_target=weekly_li_outbound_target
    )
    if not success:
        return "Failed to update weekly LI outbound target", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/update_weekly_email_outbound_target", methods=["PATCH"])
def patch_update_sdr_weekly_email_outbound_target():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    weekly_email_outbound_target: int = get_request_parameter(
        "weekly_email_outbound_target", request, json=True, required=True
    )
    success = update_client_sdr_weekly_email_outbound_target(
        client_sdr_id=client_sdr_id,
        weekly_email_outbound_target=weekly_email_outbound_target,
    )
    if not success:
        return "Failed to update weekly email outbound target", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/archetype/set_transformer_blocklist", methods=["POST"])
def post_archetype_set_transformer_blocklist():
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    new_blocklist: list = get_request_parameter(
        "new_blocklist", request, json=True, required=True
    )

    success, message = update_transformer_blocklist(
        client_archetype_id=client_archetype_id, new_blocklist=new_blocklist
    )

    if success:
        return "OK", 200

    return "400", message


@CLIENT_BLUEPRINT.route("/archetype/replicate_transformer_blocklist", methods=["POST"])
def post_archetype_replicate_transformer_blocklist():
    source_client_archetype_id = get_request_parameter(
        "source_client_archetype_id", request, json=True, required=True
    )
    destination_client_archetype_id = get_request_parameter(
        "destination_client_archetype_id", request, json=True, required=True
    )

    success, message = replicate_transformer_blocklist(
        source_client_archetype_id=source_client_archetype_id,
        destination_client_archetype_id=destination_client_archetype_id,
    )

    if success:
        return "OK", 200

    return "400", message


@CLIENT_BLUEPRINT.route("/archetype/get_ctas", methods=["POST"])
def get_ctas_endpoint():
    """Get all CTAs for a client archetype"""

    # WARNING WARNING WARNING
    # TODO(David): THIS NEEDS VERIFICATION. IT IS NOT SECURE
    try:
        client_archetype_id = get_request_parameter(
            "client_archetype_id", request, json=True, required=True, parameter_type=int
        )
    except Exception as e:
        return e.args[0], 400

    ctas: list[GeneratedMessageCTA] = get_ctas(client_archetype_id=client_archetype_id)

    return jsonify([cta.to_dict() for cta in ctas]), 200


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>/get_ctas", methods=["GET"])
@require_user
def get_ctas_by_archetype_endpoint(client_sdr_id: int, archetype_id: int):
    """Gets CTA and analytics for a given archetype id."""
    ctas: dict = get_cta_by_archetype_id(
        client_sdr_id=client_sdr_id, archetype_id=archetype_id
    )
    if ctas.get("status_code") != 200:
        return jsonify({"message": ctas.get("message")}), ctas.get("status_code")

    return (
        jsonify(
            {
                "message": "Success",
                "ctas": ctas.get("ctas"),
            }
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>/transformers", methods=["GET"])
@require_user
def get_transformers(client_sdr_id: int, archetype_id: int):
    """Gets transformers stats for an archetype"""

    email = get_request_parameter(
        "email", request, json=False, required=False
    )
    if email is None: email = False

    result = get_transformers_by_archetype_id(client_sdr_id, archetype_id, email)

    return jsonify(result), result.get('status_code')


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>/all_uploads", methods=["GET"])
@require_user
def get_all_uploads(client_sdr_id: int, archetype_id: int):
    """Gets all uploads for an archetype"""

    result = get_all_uploads_by_archetype_id(client_sdr_id, archetype_id)

    return jsonify(result), result.get('status_code')


@CLIENT_BLUEPRINT.route("/sdr/toggle_autopilot_enabled", methods=["POST"])
def post_toggle_client_sdr_autopilot_enabled():
    """Toggles autopilot enabled for a client SDR"""
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    success = toggle_client_sdr_autopilot_enabled(client_sdr_id=client_sdr_id)
    if not success:
        return "Failed to toggle autopilot enabled", 400
    return "OK", 200
