from crypt import methods
from flask import Blueprint, request, jsonify
from src.prospecting.models import Prospect
from src.client.services import (
    submit_demo_feedback,
    get_all_demo_feedback,
    get_demo_feedback_for_client,
)
from src.utils.slack import send_slack_message, URL_MAP
from src.client.services import check_nylas_status, get_client_archetype_prospects
from model_import import ClientPod
from src.message_generation.models import GeneratedMessageCTA
from src.client.services import (
    create_client,
    create_client_archetype,
    create_client_sdr,
    get_sdr_available_outbound_channels,
    rename_archetype,
    get_personas_page_details,
    toggle_archetype_active,
    complete_client_sdr_onboarding,
    clear_nylas_tokens,
    nylas_account_details,
    update_client_sdr_email,
    update_client_sdr_scheduling_link,
    update_client_pipeline_notification_webhook,
    update_client_sdr_pipeline_notification_webhook,
    get_nylas_all_events,
    populate_prospect_events,
    find_prospect_events,
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
    deactivate_client_sdr,
    activate_client_sdr,
    get_prospect_upload_stats_by_upload_id,
    get_prospect_upload_details_by_upload_id,
    get_transformers_by_archetype_id,
    get_all_uploads_by_archetype_id,
    toggle_client_sdr_autopilot_enabled,
    nylas_exchange_for_authorization_code,
    get_unused_linkedin_and_email_prospect_for_persona,
    update_persona_brain_details,
    predict_persona_fit_reason,
    generate_persona_description,
    generate_persona_buy_reason,
    generate_persona_icp_matching_prompt,
    update_do_not_contact_filters,
    get_do_not_contact_filters,
    list_prospects_caught_by_client_filters,
    remove_prospects_caught_by_client_filters,
    update_client_details,
    update_client_sdr_details,
    add_client_product,
    remove_client_product,
    get_client_products,
    update_client_product,
)
from src.client.services_unassigned_contacts_archetype import (
    predict_persona_buckets_from_client_archetype,
)
from src.client.services_client_archetype import (
    update_transformer_blocklist,
    replicate_transformer_blocklist,
    get_archetype_details_for_sdr,
)
from src.client.services_client_pod import (
    create_client_pod,
    delete_client_pod,
    add_client_sdr_to_client_pod,
    get_client_pods_for_client,
)
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.client.models import ClientArchetype, ClientSDR, Client
from app import db
import os

CLIENT_BLUEPRINT = Blueprint("client", __name__)


@CLIENT_BLUEPRINT.route("/submit-error", methods=["POST"])
@require_user
def post_submit_error(client_sdr_id: int):

    error = get_request_parameter(
        "error", request, json=True, required=True, parameter_type=str
    )
    user_agent = get_request_parameter(
        "user_agent", request, json=True, required=True, parameter_type=str
    )

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()

    send_slack_message(
        message=" An error occurred for *{client_sdr_name}*, on '{user_agent}':\n{error}".format(
            error=error,
            client_sdr_name=client_sdr.name,
            user_agent=user_agent,
        ),
        webhook_urls=[URL_MAP["user-errors"]],
    )

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
    tagline = get_request_parameter("tagline", request, json=True, required=False)
    description = get_request_parameter(
        "description", request, json=True, required=False
    )

    resp = create_client(
        company=company,
        contact_name=contact_name,
        contact_email=contact_email,
        linkedin_outbound_enabled=linkedin_outbound_enabled,
        email_outbound_enabled=email_outbound_enabled,
        tagline=tagline,
        description=description,
    )

    return jsonify(resp)


@CLIENT_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_client(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client_dict = client.to_dict()
    return jsonify(client_dict), 200


@CLIENT_BLUEPRINT.route("/", methods=["PATCH"])
@require_user
def patch_client(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    company = get_request_parameter("company", request, json=True, required=False)
    tagline = get_request_parameter("tagline", request, json=True, required=False)
    description = get_request_parameter(
        "description", request, json=True, required=False
    )
    value_prop_key_points = get_request_parameter(
        "value_prop_key_points", request, json=True, required=False
    )
    tone_attributes = get_request_parameter(
        "tone_attributes", request, json=True, required=False
    )
    mission = get_request_parameter("mission", request, json=True, required=False)
    case_study = get_request_parameter("case_study", request, json=True, required=False)

    success = update_client_details(
        client_id=client_id,
        company=company,
        tagline=tagline,
        description=description,
        value_prop_key_points=value_prop_key_points,
        tone_attributes=tone_attributes,
        mission=mission,
        case_study=case_study,
    )
    if not success:
        return "Failed to update client", 404
    return "OK", 200


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
    persona_description = get_request_parameter(
        "description", request, json=True, required=False
    )
    persona_fit_reason = get_request_parameter(
        "fit_reason", request, json=True, required=False
    )
    icp_matching_prompt = get_request_parameter(
        "icp_matching_prompt", request, json=True, required=False
    )
    persona_contact_objective = get_request_parameter(
        "contact_objective", request, json=True, required=False
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
        persona_description=persona_description,
        persona_fit_reason=persona_fit_reason,
        icp_matching_prompt=icp_matching_prompt,
        persona_contact_objective=persona_contact_objective,
    )
    if not ca:
        return "Client not found", 404

    return ca


@CLIENT_BLUEPRINT.route("/archetype/<int:archetype_id>/prospects", methods=["GET"])
@require_user
def get_archetype_prospects_endpoint(client_sdr_id: int, archetype_id: int):
    """Get all prospects, simple, for an archetype"""
    search = get_request_parameter("search", request, json=False, required=False) or ""

    prospects = get_client_archetype_prospects(client_sdr_id, archetype_id, search)

    return jsonify({"message": "Success", "prospects": prospects}), 200


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


@CLIENT_BLUEPRINT.route("/archetype/get_archetypes/overview", methods=["GET"])
@require_user
def get_archetypes_overview(client_sdr_id: int):
    """Gets an overview of all the archetypes"""

    overview = get_personas_page_details(client_sdr_id)
    return jsonify({"message": "Success", "data": overview}), 200


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


@CLIENT_BLUEPRINT.route("/sdr", methods=["PATCH"])
@require_user
def patch_sdr(client_sdr_id: int):
    name = get_request_parameter("name", request, json=True, required=False)
    email = get_request_parameter("email", request, json=True, required=False)
    title = get_request_parameter("title", request, json=True, required=False)

    success = update_client_sdr_details(
        client_sdr_id=client_sdr_id, name=name, email=email, title=title
    )
    if not success:
        return jsonify({"message": "Failed to update client SDR"}), 404
    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr/complete-onboarding", methods=["POST"])
@require_user
def post_sdr_complete_onboarding(client_sdr_id: int):

    complete_client_sdr_onboarding(client_sdr_id)

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr", methods=["POST"])
def create_sdr():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    name = get_request_parameter("name", request, json=True, required=True)
    email = get_request_parameter("email", request, json=True, required=True)

    resp = create_client_sdr(client_id=client_id, name=name, email=email)
    if not resp:
        return "Client not found", 404

    return resp


@CLIENT_BLUEPRINT.route("/sdr/deactivate", methods=["POST"])
def deactivate_sdr_endpoint():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True, parameter_type=int
    )
    email = get_request_parameter(
        "email", request, json=True, required=True, parameter_type=str
    )

    success = deactivate_client_sdr(client_sdr_id=client_sdr_id, email=email)
    if not success:
        return "Failed to deactive", 404

    return jsonify({"message": "Deactivated SDR"}), 200


@CLIENT_BLUEPRINT.route("/sdr/timezone", methods=["POST"])
@require_user
def set_sdr_timezone(client_sdr_id: int):

    timezone = get_request_parameter(
        "timezone", request, json=True, required=True, parameter_type=str
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sdr.timezone = timezone
    db.session.commit()

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr/activate", methods=["POST"])
def activate_sdr_endpoint():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True, parameter_type=int
    )
    li_sla = get_request_parameter(
        "li_sla", request, json=True, required=False, parameter_type=int
    )
    email_sla = get_request_parameter(
        "email_sla", request, json=True, required=False, parameter_type=int
    )

    success = activate_client_sdr(
        client_sdr_id=client_sdr_id, li_target=li_sla, email_target=email_sla
    )
    if not success:
        return "Failed to activate", 404

    return jsonify({"message": "Activated SDR"}), 200


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

    return jsonify(result), result.get("status_code")


@CLIENT_BLUEPRINT.route("/prospect_upload/<upload_id>/details", methods=["GET"])
@require_user
def get_prospect_upload_details(client_sdr_id: int, upload_id: int):
    """Gets prospect details of a prospect upload"""

    result = get_prospect_upload_details_by_upload_id(client_sdr_id, upload_id)

    return jsonify(result), result.get("status_code")


@CLIENT_BLUEPRINT.route("/sdr/update_scheduling_link", methods=["PATCH"])
@require_user
def patch_update_scheduling_link(client_sdr_id: int):
    scheduling_link = get_request_parameter(
        "scheduling_link", request, json=True, required=True
    )

    success = update_client_sdr_scheduling_link(
        client_sdr_id=client_sdr_id, scheduling_link=scheduling_link
    )
    if not success:
        return jsonify({"error": "Failed to update scheduling link"}), 404

    return jsonify({"message": "Scheduling link updated"}), 200


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


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>", methods=["GET"])
@require_user
def get_archetype_details_by_archetype_id(client_sdr_id: int, archetype_id: int):
    """Gets archetype details for an archetype"""
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return "Archetype not found or not owned by client SDR", 404

    result = archetype.to_dict()

    return jsonify(result), 200


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

    email = get_request_parameter("email", request, json=False, required=False)
    if email is None:
        email = False

    result = get_transformers_by_archetype_id(client_sdr_id, archetype_id, email)

    return jsonify(result), result.get("status_code")


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>/all_uploads", methods=["GET"])
@require_user
def get_all_uploads(client_sdr_id: int, archetype_id: int):
    """Gets all uploads for an archetype"""

    result = get_all_uploads_by_archetype_id(client_sdr_id, archetype_id)

    return jsonify(result), result.get("status_code")


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


@CLIENT_BLUEPRINT.route("/pod", methods=["POST"])
def post_create_pod():
    client_id: int = get_request_parameter(
        "client_id", request, json=True, required=True
    )
    name: str = get_request_parameter("name", request, json=True, required=True)
    client_pod: ClientPod = create_client_pod(
        client_id=client_id,
        name=name,
    )
    return jsonify(client_pod.to_dict()), 200


@CLIENT_BLUEPRINT.route("/pod", methods=["DELETE"])
def delete_pod():
    client_pod_id: int = get_request_parameter(
        "client_pod_id", request, json=True, required=True
    )
    success, message = delete_client_pod(client_pod_id=client_pod_id)
    if not success:
        return message, 400
    return message, 200


@CLIENT_BLUEPRINT.route("/sdr/add_to_pod", methods=["POST"])
def post_add_sdr_to_pod():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    client_pod_id: int = get_request_parameter(
        "client_pod_id", request, json=True, required=True
    )
    success = add_client_sdr_to_client_pod(
        client_sdr_id=client_sdr_id,
        client_pod_id=client_pod_id,
    )
    if not success:
        return "Failed to add SDR to pod", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/pod/get_pods", methods=["GET"])
def post_get_pods():
    client_id: int = get_request_parameter(
        "client_id", request, json=False, required=True
    )
    pods_dict = get_client_pods_for_client(client_id=client_id)
    return jsonify(pods_dict), 200


@CLIENT_BLUEPRINT.route("/nylas/check_nylas_status", methods=["GET"])
@require_user
def get_check_nylas_status(client_sdr_id: int):
    """Checks the Nylas status for a client"""
    status = check_nylas_status(client_sdr_id=client_sdr_id)
    return jsonify({"status": status}), 200


@CLIENT_BLUEPRINT.route("/nylas/get_nylas_client_id", methods=["GET"])
@require_user
def get_nylas_client_id(client_sdr_id: int):
    """Gets the Nylas client id"""

    nylas_client_id = os.environ.get("NYLAS_CLIENT_ID")
    return jsonify({"nylas_client_id": nylas_client_id}), 200


@CLIENT_BLUEPRINT.route("/nylas/exchange_for_authorization_code", methods=["POST"])
@require_user
def post_nylas_exchange_for_authorization_code(client_sdr_id: int):
    """Exchanges for an authorization code from Nylas"""
    code: str = get_request_parameter(
        "nylas_code", request, json=True, required=True, parameter_type=str
    )
    success, response = nylas_exchange_for_authorization_code(
        client_sdr_id=client_sdr_id,
        code=code,
    )
    if not success:
        return (
            jsonify(response),
            int(response.get("status_code") or 400),
        )
    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/nylas/auth_tokens", methods=["DELETE"])
@require_user
def clear_auth_tokens(client_sdr_id: int):
    """Clears the Nylas auth tokens for a SDR"""

    status_text, status = clear_nylas_tokens(client_sdr_id)

    return jsonify({"message": status_text}), status


@CLIENT_BLUEPRINT.route("/nylas/account_details", methods=["GET"])
@require_user
def get_nylas_account_details(client_sdr_id: int):
    """Gets Nylas account details for an SDR"""

    data = nylas_account_details(client_sdr_id)

    return jsonify({"message": "Success", "data": data}), 200


@CLIENT_BLUEPRINT.route("/nylas/events", methods=["GET"])
@require_user
def get_nylas_events(client_sdr_id: int):
    """Gets all calendar events for an SDR"""

    return get_nylas_all_events(client_sdr_id)


@CLIENT_BLUEPRINT.route("/sdr/find_event", methods=["GET"])
@require_user
def get_prospect_event(client_sdr_id: int):
    """Finds a calendar event for a prospect"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True, parameter_type=int
    )

    events = find_prospect_events(client_sdr_id, prospect_id)
    if events is None:
        return jsonify({"message": "Failed to find event"}), 404

    return jsonify({"message": "Success", "data": events}), 200


@CLIENT_BLUEPRINT.route("/sdr/populate_events", methods=["POST"])
@require_user
def post_populate_prospect_events(client_sdr_id: int):
    """Populates the db with the prospect's calendar events"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    count = populate_prospect_events(client_sdr_id, prospect_id)

    return jsonify({"message": "Success", "data": count}), 201


@CLIENT_BLUEPRINT.route("/unused_li_and_email_prospects_count", methods=["GET"])
@require_user
def get_unused_li_and_email_prospects_count(client_sdr_id: int):
    """Gets unused LI and email prospects count for a client"""
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    data = get_unused_linkedin_and_email_prospect_for_persona(
        client_archetype_id=client_archetype_id
    )
    return jsonify(data)


@CLIENT_BLUEPRINT.route(
    "/archetype/<archetype_id>/update_description_and_fit", methods=["POST"]
)
@require_user
def post_update_persona_details(client_sdr_id: int, archetype_id: int):
    """Updates the description and fit for an archetype"""
    updated_persona_name = get_request_parameter(
        "updated_persona_name", request, json=True, required=False
    )
    updated_persona_description = get_request_parameter(
        "updated_persona_description", request, json=True, required=False
    )
    updated_persona_fit_reason = get_request_parameter(
        "updated_persona_fit_reason", request, json=True, required=False
    )
    updated_persona_icp_matching_prompt = get_request_parameter(
        "updated_persona_icp_matching_prompt", request, json=True, required=False
    )
    updated_persona_contact_objective = get_request_parameter(
        "updated_persona_contact_objective", request, json=True, required=False
    )

    success = update_persona_brain_details(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        updated_persona_name=updated_persona_name,
        updated_persona_description=updated_persona_description,
        updated_persona_fit_reason=updated_persona_fit_reason,
        updated_persona_icp_matching_prompt=updated_persona_icp_matching_prompt,
        updated_persona_contact_objective=updated_persona_contact_objective,
    )

    if success:
        return "OK", 200

    return "Failed to update description and fit", 400


@CLIENT_BLUEPRINT.route(
    "/archetype/<archetype_id>/predict_persona_fit_reason", methods=["GET"]
)
@require_user
def get_predict_persona_fit_reason(client_sdr_id: int, archetype_id: int):
    """Predicts the fit reason for an archetype"""
    success, message = predict_persona_fit_reason(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
    )

    if not success:
        return message, 400

    return jsonify({"reason": message}), 200


@CLIENT_BLUEPRINT.route("/archetype/generate_persona_description", methods=["POST"])
@require_user
def post_generate_persona_description(client_sdr_id: int):
    """Generates a persona description"""
    persona_name = get_request_parameter(
        "persona_name", request, json=True, required=True
    )
    message = generate_persona_description(
        client_sdr_id=client_sdr_id,
        persona_name=persona_name,
    )

    if not message:
        return "Failed to generate", 400

    return jsonify({"description": message})


@CLIENT_BLUEPRINT.route("/archetype/generate_persona_buy_reason", methods=["POST"])
@require_user
def post_generate_persona_buy_reason(client_sdr_id: int):
    """Generates a persona description"""
    persona_name = get_request_parameter(
        "persona_name", request, json=True, required=True
    )
    message = generate_persona_buy_reason(
        client_sdr_id=client_sdr_id,
        persona_name=persona_name,
    )

    if not message:
        return "Failed to generate", 400

    return jsonify({"description": message})


@CLIENT_BLUEPRINT.route(
    "/archetype/generate_persona_icp_matching_prompt", methods=["POST"]
)
@require_user
def post_generate_persona_icp_matching_prompt(client_sdr_id: int):
    """Generates a persona description"""
    persona_name = get_request_parameter(
        "persona_name", request, json=True, required=True
    )
    persona_description = get_request_parameter(
        "persona_description", request, json=True, required=False
    )
    persona_buy_reason = get_request_parameter(
        "persona_buy_reason", request, json=True, required=False
    )
    message = generate_persona_icp_matching_prompt(
        client_sdr_id=client_sdr_id,
        persona_name=persona_name,
        persona_description=persona_description,
        persona_buy_reason=persona_buy_reason,
    )

    if not message:
        return "Failed to generate", 400

    return jsonify({"description": message})


@CLIENT_BLUEPRINT.route(
    "/archetype/predict_persona_buckets_from_client_archetype", methods=["POST"]
)
@require_user
def post_predict_persona_buckets_from_client_archetype(client_sdr_id: int):
    """Predicts the persona buckets from a client archetype's prospects"""
    from model_import import ClientArchetype

    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )

    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Invalid client archetype", 400

    success, data = predict_persona_buckets_from_client_archetype(
        client_archetype_id=client_archetype_id,
    )

    if not success:
        return data, 400

    return jsonify({"data": data}), 200


@CLIENT_BLUEPRINT.route("/archetype/get_details", methods=["GET"])
@require_user
def get_archetype_details(client_sdr_id: int):
    """Gets the archetype details"""
    data = get_archetype_details_for_sdr(
        client_sdr_id=client_sdr_id,
    )

    return jsonify({"data": data}), 200


@CLIENT_BLUEPRINT.route("/demo_feedback", methods=["POST"])
@require_user
def post_demo_feedback(client_sdr_id: int):
    """Submits demo feedback"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    status = get_request_parameter(
        "status", request, json=True, required=True, parameter_type=str
    )
    rating = get_request_parameter(
        "rating", request, json=True, required=True, parameter_type=str
    )
    feedback = get_request_parameter(
        "feedback", request, json=True, required=True, parameter_type=str
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    prospect: Prospect = Prospect.query.get(prospect_id)

    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect not found"}), 400

    result = submit_demo_feedback(
        client_id=client_sdr.client_id,
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        status=status,
        rating=rating,
        feedback=feedback,
    )

    send_slack_message(
        message=f"""
        ✍️ New demo feedback via {client_sdr.name}!
        _Details_
        With {prospect.full_name} on {str(prospect.demo_date)}

        _Did the demo happen?_
        {status}

        _How did it go?_
        {rating}

        _What did you like / what would you change?_
        {feedback}
        """,
        webhook_urls=[URL_MAP["csm-demo-feedback"]],
    )

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/demo_feedback", methods=["GET"])
@require_user
def get_demo_feedback(client_sdr_id: int):
    """Get demo feedback"""

    all_feedback = get_all_demo_feedback(client_sdr_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": [feedback.to_dict() for feedback in all_feedback],
            }
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/do_not_contact_filters", methods=["POST"])
@require_user
def post_do_not_contact_filters(client_sdr_id: int):
    """Gets the archetype details"""
    do_not_contact_keywords_in_company_names = get_request_parameter(
        "do_not_contact_keywords_in_company_names", request, json=True, required=False
    )
    do_not_contact_company_names = get_request_parameter(
        "do_not_contact_company_names", request, json=True, required=False
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    success = update_do_not_contact_filters(
        client_id=client_id,
        do_not_contact_keywords_in_company_names=do_not_contact_keywords_in_company_names,
        do_not_contact_company_names=do_not_contact_company_names,
    )
    if not success:
        return "Failed to update do not contact filters", 400

    return "OK", 200


@CLIENT_BLUEPRINT.route("/do_not_contact_filters", methods=["GET"])
@require_user
def get_do_not_contact_filters_endpoint(client_sdr_id: int):
    """Gets the archetype details"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    data = get_do_not_contact_filters(
        client_id=client_id,
    )
    return jsonify({"data": data}), 200


@CLIENT_BLUEPRINT.route("/do_not_contact_filters/caught_prospects", methods=["GET"])
@require_user
def get_caught_prospects_endpoint(client_sdr_id: int):
    """Gets the archetype details"""
    prospects = list_prospects_caught_by_client_filters(
        client_sdr_id=client_sdr_id,
    )
    return jsonify({"prospects": prospects}), 200


@CLIENT_BLUEPRINT.route("/do_not_contact_filters/remove_prospects", methods=["POST"])
@require_user
def post_remove_prospects_endpoint(client_sdr_id: int):
    """Removes prospects from the do not contact filters"""
    success = remove_prospects_caught_by_client_filters(
        client_sdr_id=client_sdr_id,
    )
    if not success:
        return "Failed to remove prospects", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/product", methods=["POST"])
@require_user
def post_client_product(client_sdr_id: int):

    name = get_request_parameter(
        "name", request, json=True, required=True, default_value=""
    )
    description = get_request_parameter(
        "description", request, json=True, required=True, default_value=""
    )
    how_it_works = get_request_parameter(
        "how_it_works", request, json=True, required=False, default_value=None
    )
    use_cases = get_request_parameter(
        "use_cases", request, json=True, required=False, default_value=None
    )
    product_url = get_request_parameter(
        "product_url", request, json=True, required=False, default_value=None
    )

    success = add_client_product(
        client_sdr_id=client_sdr_id,
        name=name,
        description=description,
        how_it_works=how_it_works,
        use_cases=use_cases,
        product_url=product_url,
    )
    if not success:
        return jsonify({"message": "Failed to add new product"}), 500

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/product", methods=["PUT"])
@require_user
def put_client_product(client_sdr_id: int):

    product_id = get_request_parameter(
        "product_id", request, json=True, required=True, parameter_type=int
    )

    name = get_request_parameter(
        "name", request, json=True, required=False, default_value=None
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, default_value=None
    )
    how_it_works = get_request_parameter(
        "how_it_works", request, json=True, required=False, default_value=None
    )
    use_cases = get_request_parameter(
        "use_cases", request, json=True, required=False, default_value=None
    )
    product_url = get_request_parameter(
        "product_url", request, json=True, required=False, default_value=None
    )

    success = update_client_product(
        client_sdr_id=client_sdr_id,
        client_product_id=product_id,
        name=name,
        description=description,
        how_it_works=how_it_works,
        use_cases=use_cases,
        product_url=product_url,
    )
    if not success:
        return jsonify({"message": "Failed to update product"}), 500

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/product", methods=["DELETE"])
@require_user
def delete_client_product(client_sdr_id: int):

    product_id = get_request_parameter("product_id", request, json=True, required=True)

    success = remove_client_product(
        client_sdr_id=client_sdr_id, client_product_id=product_id
    )
    if not success:
        return jsonify({"message": "Failed to remove product"}), 500

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/product", methods=["GET"])
@require_user
def get_client_product(client_sdr_id: int):

    products = get_client_products(client_sdr_id=client_sdr_id)

    return jsonify({"message": "Success", "data": products}), 200


@CLIENT_BLUEPRINT.route("/demo_feedback", methods=["GET"])
@require_user
def get_demo_feedback_endpoint(client_sdr_id: int):
    """Get demo feedback"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    all_feedback = get_demo_feedback_for_client(client_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": all_feedback,
            }
        ),
        200,
    )
