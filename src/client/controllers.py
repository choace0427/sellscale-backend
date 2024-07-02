from crypt import methods
from datetime import datetime
from pydoc import cli
from typing import Optional
from debugpy import connect
from flask import Blueprint, request, jsonify
from numpy import require
from src.client.sdr.email.services_email_bank import (
    nylas_exchange_for_authorization_code,
)
from sqlalchemy.orm.attributes import flag_modified
from src.client.sdr.services_client_sdr import update_sdr_blacklist_words
from src.personas.services import (
    clone_persona,
)
from src.prospecting.models import Prospect
from src.client.services import (
    create_archetype_asset,
    create_client_archetype_reason_mapping,
    delete_archetype_asset,
    delete_client_asset_archetype_mapping,
    get_available_times_via_calendly,
    get_client_archetypes_for_entire_client,
    get_client_assets,
    get_tam_data,
    modify_client_archetype_reason_mapping,
    msg_analytics_report,
    get_testing_volume,
    modify_testing_volume,
    remove_prospects_caught_by_filters,
    toggle_client_sdr_auto_send_email_campaign,
    update_asset,
    update_client_auto_generate_email_messages_setting,
    update_client_sdr_territory_name,
)
from src.client.services_client_archetype import (
    auto_turn_off_finished_archetypes,
    fetch_all_assets_in_client,
    get_email_to_linkedin_connection_amounts,
    set_email_to_linkedin_connection,
    set_personalizers_enabled,
)
from src.personas.services_persona import link_asset_to_persona
from src.prospecting.services import create_note
from src.automation.resend import send_email
from src.client.services import (
    edit_demo_feedback,
    import_pre_onboarding,
    submit_demo_feedback,
    get_all_demo_feedback,
    get_demo_feedback,
    get_demo_feedback_for_client,
    toggle_client_sdr_auto_bump,
    toggle_client_sdr_auto_send_linkedin_campaign,
    toggle_is_onboarding,
    update_client_auto_generate_li_messages_setting,
    update_client_sdr_cc_bcc_emails,
    update_phantom_buster_launch_schedule,
    write_client_pre_onboarding_survey,
)
from src.vision.services import attempt_chat_completion_with_vision
from src.client.services import mark_prospect_removed
from src.slack.models import SlackNotificationType
from src.slack.notifications.demo_feedback_collected import (
    DemoFeedbackCollectedNotification,
)
from src.slack.notifications.demo_feedback_updated import (
    DemoFeedbackUpdatedNotification,
)
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)
from src.client.services_assets import generate_client_assets, generate_client_offers
from src.utils.datetime.dateparse_utils import convert_string_to_datetime
from src.utils.slack import send_slack_message, URL_MAP
from src.client.services import check_nylas_status, get_client_archetype_prospects
from model_import import ClientPod
from src.message_generation.models import GeneratedMessageCTA
from src.client.services import (
    update_client_sdr_supersight_link,
    create_client,
    create_client_archetype,
    create_client_sdr,
    get_sdr_available_outbound_channels,
    get_sdr_calendar_availability,
    rename_archetype,
    onboarding_setup_completion_report,
    get_personas_page_details,
    toggle_archetype_active,
    complete_client_sdr_onboarding,
    clear_nylas_tokens,
    populate_single_prospect_event,
    nylas_account_details,
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
    get_personas_page_campaigns,
    get_ctas,
    get_client_archetypes,
    get_cta_by_archetype_id,
    get_client_sdr,
    find_sdr_events,
    deactivate_client_sdr,
    activate_client_sdr,
    get_prospect_upload_stats_by_upload_id,
    get_prospect_upload_details_by_upload_id,
    get_transformers_by_archetype_id,
    get_all_uploads_by_archetype_id,
    toggle_client_sdr_autopilot_enabled,
    get_unused_linkedin_and_email_prospect_for_persona,
    update_persona_brain_details,
    predict_persona_fit_reason,
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
    get_persona_setup_status_map_for_persona,
    get_client_sdr_table_info,
    update_sdr_conversion_percentages,
    update_sdr_do_not_contact_filters,
    get_sdr_do_not_contact_filters,
    list_prospects_caught_by_sdr_client_filters,
    remove_prospects_caught_by_sdr_client_filters,
    update_archetype_emoji,
    get_spending,
    get_all_clients
)
from src.client.services_unassigned_contacts_archetype import (
    predict_persona_buckets_from_client_archetype,
)
from src.client.services_client_archetype import (
    activate_client_archetype,
    create_empty_archetype_prospect_filters,
    deactivate_client_archetype,
    fetch_archetype_assets,
    get_archetype_activity,
    get_archetype_conversion_rates,
    get_client_archetype_stats,
    get_client_archetype_overview,
    is_archetype_uploading_contacts,
    get_client_archetype_sequences,
    get_client_archetype_analytics,
    get_sent_volume_during_time_period,
    get_client_archetype_contacts,
    get_total_contacts_for_archetype,
    get_email_blocks_configuration,
    hard_deactivate_client_archetype,
    modify_archetype_prospect_filters,
    overall_activity_for_client,
    patch_archetype_email_blocks_configuration,
    update_transformer_blocklist,
    replicate_transformer_blocklist,
    update_transformer_blocklist_initial,
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
from src.client.models import (
    ClientArchetype,
    ClientAssetType,
    ClientAssets,
    ClientSDR,
    Client,
    DemoFeedback,
)
from app import db
import os

CLIENT_BLUEPRINT = Blueprint("client", __name__)


@CLIENT_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_clients(client_sdr_id: int):

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr or sdr.client_id != 1:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Unauthorized access.",
                }
            ),
            401,
        )

    clients: list[Client] = Client.query.all()

    return (
        jsonify(
            {
                "message": "Success",
                "data": [client.to_dict() for client in clients],
            }
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/sdrs", methods=["GET"])
@require_user
def get_sdrs(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    sdrs: list[ClientSDR] = (
        ClientSDR.query.filter_by(client_id=client_id).filter_by(active=True).all()
    )

    # inbox_stats_query = """
    # select
    #     client_sdr.id,
    #     client_sdr.name,
    #     count(distinct prospect.id) unread_inbox_messages
    # from prospect
    #     join client_sdr on client_sdr.id = prospect.client_sdr_id
    # where prospect.overall_status = 'ACTIVE_CONVO'
    #     and (
    #         prospect.hidden_until is null or
    #         prospect.hidden_until < NOW()
    #     )
    #     and client_sdr.client_id = {client_id}
    # group by 1;
    # """
    # inbox_stats = db.engine.execute(inbox_stats_query.format(client_id=client_id)).fetchall()

    # data = [sdr.to_dict() for sdr in sdrs]
    # for row in inbox_stats:
    #     for sdr in data:
    #         if sdr["id"] == row[0]:
    #             sdr["unread_inbox_messages"] = row[2]

    data = [sdr.to_dict() for sdr in sdrs]
    from src.sight_inbox.services import get_inbox_prospects

    for sdr in data:
        details = get_inbox_prospects(sdr["id"])
        sdr["unread_inbox_messages"] = len(details.get("manual_bucket", []))

    return jsonify({"message": "Success", "data": data}), 200


@CLIENT_BLUEPRINT.route("/all_archetypes", methods=["GET"])
@require_user
def get_client_all_archetypes(client_sdr_id: int):

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Unauthorized access.",
                }
            ),
            401,
        )

    client_id = sdr.client_id

    if client_id:
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter_by(
            client_id=client_id
        ).all()
    else:
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter_by(
            client_sdr_id=client_sdr_id
        ).all()

    return (
        jsonify(
            {
                "message": "Success",
                "data": [archetype.to_dict() for archetype in archetypes],
            }
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/sdr_access", methods=["GET"])
@require_user
def get_client_sdr_access(client_sdr_id: int):

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr or sdr.client_id != 1:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Unauthorized access.",
                }
            ),
            401,
        )

    client_id = get_request_parameter(
        "client_id", request, json=False, required=True, parameter_type=int
    )

    other_sdr: ClientSDR = ClientSDR.query.filter_by(client_id=client_id).first()

    return (
        jsonify(
            {
                "message": "Success",
                "data": {"token": other_sdr.auth_token},
            }
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/linkedin/auto_generate", methods=["PATCH"])
@require_user
def patch_linkedin_auto_generate(client_sdr_id: int):
    auto_generate = get_request_parameter(
        "auto_generate", request, json=True, required=True, parameter_type=bool
    )

    success = update_client_auto_generate_li_messages_setting(
        client_sdr_id=client_sdr_id, auto_generate_li_messages=auto_generate
    )
    if not success:
        return "Failed to update client SDR", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/email/auto_generate", methods=["PATCH"])
@require_user
def patch_email_auto_generate(client_sdr_id: int):
    auto_generate = get_request_parameter(
        "auto_generate", request, json=True, required=True, parameter_type=bool
    )

    success = update_client_auto_generate_email_messages_setting(
        client_sdr_id=client_sdr_id, auto_generate_email_messages=auto_generate
    )
    if not success:
        return "Failed to update client SDR", 404
    return "OK", 200


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
    company_website = get_request_parameter(
        "company_website", request, json=True, required=True
    )
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
        company_website=company_website,
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


@CLIENT_BLUEPRINT.route("/brain", methods=["GET"])
@require_user
def get_ai_brain(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client: Client = Client.query.get(client_id)

    name = client.company
    tagline = client.tagline
    description = client.description

    return {"name": name, "tagline": tagline, "description": description}


@CLIENT_BLUEPRINT.route("/", methods=["PATCH"])
@require_user
def patch_client(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    company = get_request_parameter("company", request, json=True, required=False)
    company_website = get_request_parameter(
        "company_website", request, json=True, required=False
    )
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
    contract_size = get_request_parameter(
        "contract_size", request, json=True, required=False
    )

    success = update_client_details(
        client_id=client_id,
        company=company,
        company_website=company_website,
        tagline=tagline,
        description=description,
        value_prop_key_points=value_prop_key_points,
        tone_attributes=tone_attributes,
        mission=mission,
        case_study=case_study,
        contract_size=contract_size,
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
    persona_fit_reason = get_request_parameter(
        "fit_reason", request, json=True, required=False
    )
    icp_matching_prompt = get_request_parameter(
        "icp_matching_prompt", request, json=True, required=False
    )
    persona_contact_objective = get_request_parameter(
        "contact_objective", request, json=True, required=False
    )
    persona_contract_size = get_request_parameter(
        "contract_size", request, json=True, required=False
    )
    template_mode = get_request_parameter(
        "template_mode", request, json=True, required=False
    )
    linkedin_active = get_request_parameter(
        "linkedin_active", request, json=True, required=False
    )
    email_active = get_request_parameter(
        "email_active", request, json=True, required=False
    )
    email_to_linkedin_connection = get_request_parameter(
        "email_to_linkedin_connection", request, json=True, required=False
    )
    purpose = get_request_parameter("purpose", request, json=True, required=False)
    

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
        persona_fit_reason=persona_fit_reason,
        icp_matching_prompt=icp_matching_prompt,
        persona_contact_objective=persona_contact_objective,
        persona_contract_size=persona_contract_size,
        template_mode=template_mode,
        linkedin_active=linkedin_active,
        email_active=email_active,
        connection_type=email_to_linkedin_connection,
        purpose=purpose,
    )
    if not ca:
        return "Client not found", 404

    return ca


@CLIENT_BLUEPRINT.route(
    "/archetype/<int:archetype_id>/update_email_to_linkedin_connection",
    methods=["PATCH"],
)
@require_user
def patch_update_email_to_linkedin_connection(client_sdr_id: int, archetype_id: int):
    email_to_linkedin_connection = get_request_parameter(
        "email_to_linkedin_connection", request, json=True, required=True
    )

    set_email_to_linkedin_connection(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        connection_type=email_to_linkedin_connection,
    )
    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route(
    "/archetype/<int:archetype_id>/email_to_linkedin_connection_amounts",
    methods=["GET"],
)
@require_user
def email_to_linkedin_connection_amounts(client_sdr_id: int, archetype_id: int):
    email_to_linkedin_connection_amounts = get_email_to_linkedin_connection_amounts(
        client_sdr_id=client_sdr_id, client_archetype_id=archetype_id
    )
    return (
        jsonify({"message": "Success", "data": email_to_linkedin_connection_amounts}),
        200,
    )

@CLIENT_BLUEPRINT.route(
    "/archetype/<int:archetype_id>/update_personalizers_enabled", methods=["PATCH"]
)
@require_user
def patch_update_personalizers_enabled(client_sdr_id: int, archetype_id: int):
    personalizers_enabled = get_request_parameter(
        "personalizers_enabled", request, json=True, required=True
    )

    set_personalizers_enabled(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        personalizers_enabled=personalizers_enabled,
    )
    return jsonify({"message": "Success"}), 200

# toggle template mode active for archetype
@CLIENT_BLUEPRINT.route(
    "/archetype/<int:archetype_id>/toggle_template_mode", methods=["PATCH"]
)
@require_user
def patch_toggle_template_mode(client_sdr_id: int, archetype_id: int):
    template_mode = get_request_parameter(
        "template_mode", request, json=True, required=True, parameter_type=bool
    )

    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not client_archetype or client_archetype.client_sdr_id != client_sdr_id:
        return "Failed to find archetype", 404

    client_archetype.template_mode = template_mode
    db.session.add(client_archetype)
    db.session.commit()

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/archetype/<int:archetype_id>/prospects", methods=["GET"])
@require_user
def get_archetype_prospects_endpoint(client_sdr_id: int, archetype_id: int):
    """Get all prospects, simple, for an archetype"""
    search = get_request_parameter("search", request, json=False, required=False) or ""

    prospects = get_client_archetype_prospects(client_sdr_id, archetype_id, search)

    return jsonify({"message": "Success", "prospects": prospects}), 200


@CLIENT_BLUEPRINT.route("/archetype/<int:archetype_id>/clone", methods=["POST"])
@require_user
def post_archetype_clone_endpoint(client_sdr_id: int, archetype_id: int):
    persona_name = get_request_parameter(
        "persona_name", request, json=True, required=True, parameter_type=str
    )
    persona_fit_reason = get_request_parameter(
        "persona_fit_reason", request, json=True, required=True, parameter_type=str
    )
    persona_icp_matching_instructions = get_request_parameter(
        "persona_icp_matching_instructions",
        request,
        json=True,
        required=True,
        parameter_type=str,
    )
    persona_contact_objective = get_request_parameter(
        "persona_contact_objective",
        request,
        json=True,
        required=True,
        parameter_type=str,
    )

    option_ctas = get_request_parameter(
        "option_ctas", request, json=True, required=True, parameter_type=bool
    )
    option_bump_frameworks = get_request_parameter(
        "option_bump_frameworks", request, json=True, required=True, parameter_type=bool
    )
    option_voices = get_request_parameter(
        "option_voices", request, json=True, required=True, parameter_type=bool
    )
    option_email_blocks = get_request_parameter(
        "option_email_blocks", request, json=True, required=True, parameter_type=bool
    )
    option_icp_filters = get_request_parameter(
        "option_icp_filters", request, json=True, required=True, parameter_type=bool
    )
    option_email_steps = (
        get_request_parameter(
            "option_email_steps",
            request,
            json=True,
            required=False,
            parameter_type=bool,
        )
        or False
    )
    option_li_init_msg = (
        get_request_parameter(
            "option_li_init_msg",
            request,
            json=True,
            required=False,
            parameter_type=bool,
        )
        or False
    )
    option_email_subject_lines = (
        get_request_parameter(
            "option_email_subject_lines",
            request,
            json=True,
            required=False,
            parameter_type=bool,
        )
        or False
    )

    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not client_archetype:
        return "Failed to find archetype", 404

    # ensure that client_archetype's client_id is same as client_sdr's client_id
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if client_archetype.client_id != client_sdr.client_id:
        return "Client Archetype does not belong to client", 404

    persona = clone_persona(
        client_sdr_id=client_sdr_id,
        original_persona_id=archetype_id,
        persona_name=persona_name,
        persona_fit_reason=persona_fit_reason,
        persona_icp_matching_instructions=persona_icp_matching_instructions,
        persona_contact_objective=persona_contact_objective,
        option_ctas=option_ctas,
        option_bump_frameworks=option_bump_frameworks,
        option_voices=option_voices,
        option_email_blocks=option_email_blocks,
        option_icp_filters=option_icp_filters,
        option_email_steps=option_email_steps,
        option_li_init_msg=option_li_init_msg,
        option_email_subject_lines=option_email_subject_lines,
    )
    if not persona:
        return "Failed to clone archetype", 500

    return (
        jsonify(
            {
                "message": "Success",
                "data": {
                    "archetype": persona.to_dict(),
                },
            }
        ),
        200,
    )


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


@CLIENT_BLUEPRINT.route("/archetype/get_archetypes_for_entire_client", methods=["GET"])
@require_user
def get_archetypes_for_entire_client(client_sdr_id: int):
    """Gets all the archetypes in the entire client"""
    archetypes = get_client_archetypes_for_entire_client(client_sdr_id=client_sdr_id)
    return jsonify({"message": "Success", "archetypes": archetypes}), 200


@CLIENT_BLUEPRINT.route("/archetype/get_archetype", methods=["GET"])
@require_user
def get_archetype(client_sdr_id: int):
    """Gets a single archetype for a client SDR, with indepth details"""
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True, parameter_type=int
    )

    archetype = get_archetype_conversion_rates(
        client_sdr_id=client_sdr_id, archetype_id=archetype_id
    )
    return jsonify({"message": "Success", "archetype": archetype}), 200


@CLIENT_BLUEPRINT.route("/overall/activity", methods=["GET"])
@require_user
def get_overall_client_activity(client_sdr_id: int):
    """Gets all the archetypes for a client SDR, with option to search filter by archetype name"""
    activities = get_archetype_activity(client_sdr_id=client_sdr_id)
    overall_activity = overall_activity_for_client(client_sdr_id=client_sdr_id)
    return (
        jsonify(
            {
                "message": "Success",
                "data": {
                    "activities": activities,
                    "overall_activity": [overall_activity.get("merged")],
                    "separated_overall_activity": overall_activity,
                },
            }
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/archetype/get_archetypes/overview", methods=["GET"])
@require_user
def get_archetypes_overview(client_sdr_id: int):
    """Gets an overview of all the archetypes"""

    overview = get_personas_page_details(client_sdr_id)
    return jsonify({"message": "Success", "data": overview}), 200


@CLIENT_BLUEPRINT.route("/archetype/get_archetypes/campaign_view", methods=["GET"])
@require_user
def get_archetypes_campaign_view(client_sdr_id: int):
    """Gets campaign view of all the archetypes"""

    response = get_personas_page_campaigns(client_sdr_id)
    return jsonify(response), 200


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

    sdr_id = get_request_parameter(
        "sdr_id", request, json=True, required=False, parameter_type=int
    )

    name = get_request_parameter("name", request, json=True, required=False)
    title = get_request_parameter("title", request, json=True, required=False)

    ai_outreach = get_request_parameter(
        "ai_outreach", request, json=True, required=False, parameter_type=bool
    )
    browser_extension_ui_overlay = get_request_parameter(
        "browser_extension_ui_overlay",
        request,
        json=True,
        required=False,
        parameter_type=bool,
    )

    disable_ai_on_prospect_respond = get_request_parameter(
        "disable_ai_on_prospect_respond",
        request,
        json=True,
        required=False,
        parameter_type=bool,
    )
    disable_ai_on_message_send = get_request_parameter(
        "disable_ai_on_message_send",
        request,
        json=True,
        required=False,
        parameter_type=bool,
    )

    auto_archive_convos = get_request_parameter(
        "auto_archive_convos",
        request,
        json=True,
        required=False,
        parameter_type=bool,
    )

    meta_data = get_request_parameter(
        "meta_data",
        request,
        json=True,
        required=False,
    )

    role = get_request_parameter(
        "role",
        request,
        json=True,
        required=False,
    )

    email = get_request_parameter(
        "email",
        request,
        json=True,
        required=False,
    )

    success = update_client_sdr_details(
        client_sdr_id=sdr_id or client_sdr_id,
        name=name,
        title=title,
        email=email,
        disable_ai_on_prospect_respond=disable_ai_on_prospect_respond,
        disable_ai_on_message_send=disable_ai_on_message_send,
        ai_outreach=ai_outreach,
        browser_extension_ui_overlay=browser_extension_ui_overlay,
        auto_archive_convos=auto_archive_convos,
        role=role,
        meta_data=meta_data,
    )
    if not success:
        return jsonify({"message": "Failed to update client SDR"}), 404
    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr/conversion_percentages", methods=["PATCH"])
@require_user
def patch_sdr_conversion_percentages(client_sdr_id: int):
    active_convo = get_request_parameter(
        "active_convo", request, json=True, required=True, parameter_type=float
    )
    scheduling = get_request_parameter(
        "scheduling", request, json=True, required=True, parameter_type=float
    )
    demo_set = get_request_parameter(
        "demo_set", request, json=True, required=True, parameter_type=float
    )
    demo_won = get_request_parameter(
        "demo_won", request, json=True, required=True, parameter_type=float
    )
    not_interested = get_request_parameter(
        "not_interested", request, json=True, required=True, parameter_type=float
    )

    success = update_sdr_conversion_percentages(
        client_sdr_id=client_sdr_id,
        active_convo=active_convo,
        scheduling=scheduling,
        demo_set=demo_set,
        demo_won=demo_won,
        not_interested=not_interested,
    )
    if not success:
        return jsonify({"message": "Failed to update client SDR"}), 404
    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr/general_info", methods=["GET"])
@require_user
def get_sdr_general_info(client_sdr_id: int):
    """Gets the client SDR general info"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    sdr_info = get_client_sdr_table_info(client_sdr_id)
    return jsonify({"message": "Success", "data": sdr_info}), 200


@CLIENT_BLUEPRINT.route("/sdr/complete-onboarding", methods=["POST"])
@require_user
def post_sdr_complete_onboarding(client_sdr_id: int):
    complete_client_sdr_onboarding(client_sdr_id)

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr/toggle_is_onboarding", methods=["POST"])
@require_user
def post_toggle_is_onboarding(client_sdr_id: int):
    toggle_is_onboarding(client_sdr_id)

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr", methods=["POST"])
def create_sdr():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    name = get_request_parameter("name", request, json=True, required=True)
    email = get_request_parameter("email", request, json=True, required=True)

    create_managed_inboxes = get_request_parameter(
        "create_managed_inboxes", request, json=True, required=False
    )

    include_connect_li_card = get_request_parameter(
        "include_connect_li_card", request, json=True, required=False
    )
    include_connect_slack_card = get_request_parameter(
        "include_connect_slack_card", request, json=True, required=False
    )
    include_input_pre_filters_card = get_request_parameter(
        "include_input_pre_filters_card", request, json=True, required=False
    )
    include_add_dnc_filters_card = get_request_parameter(
        "include_add_dnc_filters_card", request, json=True, required=False
    )
    include_add_calendar_link_card = get_request_parameter(
        "include_add_calendar_link_card", request, json=True, required=False
    )

    resp = create_client_sdr(
        client_id=client_id,
        name=name,
        email=email,
        create_managed_inboxes=create_managed_inboxes,
        include_connect_li_card=include_connect_li_card,
        include_connect_slack_card=include_connect_slack_card,
        include_input_pre_filters_card=include_input_pre_filters_card,
        include_add_dnc_filters_card=include_add_dnc_filters_card,
        include_add_calendar_link_card=include_add_calendar_link_card,
    )
    if not resp:
        return "Client not found", 404

    return resp


@CLIENT_BLUEPRINT.route("/sdr/add_seat", methods=["POST"])
@require_user
def post_add_seat(client_sdr_id: int):
    name = get_request_parameter("name", request, json=True, required=True)
    linkedin_url = get_request_parameter(
        "linkedin_url", request, json=True, required=True
    )
    email = get_request_parameter("email", request, json=True, required=True)

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    resp = create_client_sdr(
        client_id=sdr.client_id,
        name=name,
        email=email,
        create_managed_inboxes=True,
        include_connect_li_card=True,
        include_connect_slack_card=True,
        include_input_pre_filters_card=True,
        include_add_dnc_filters_card=True,
        include_add_calendar_link_card=True,
        linkedin_url=linkedin_url,
    )
    if not resp:
        return "Client not found", 404

    return resp


@CLIENT_BLUEPRINT.route("/sdr/activate_seat", methods=["POST"])
@require_user
def post_activate_seat(client_sdr_id: int):

    sdr_id = get_request_parameter(
        "sdr_id", request, json=True, required=False, parameter_type=int
    )

    success = activate_client_sdr(client_sdr_id=sdr_id or client_sdr_id)

    if not success:
        return "Failed to activate seat", 404
    return jsonify({"message": "Activated seat"}), 200


@CLIENT_BLUEPRINT.route("/sdr/deactivate_seat", methods=["POST"])
@require_user
def post_deactivate_seat(client_sdr_id: int):

    sdr_id = get_request_parameter(
        "sdr_id", request, json=True, required=False, parameter_type=int
    )

    client_sdr: ClientSDR = ClientSDR.query.get(sdr_id or client_sdr_id)
    email = client_sdr.email
    success = deactivate_client_sdr(client_sdr_id=client_sdr.id, email=email)

    if not success:
        return "Failed to deactivate seat", 404
    return jsonify({"message": "Deactivated seat"}), 200


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

    update_phantom_buster_launch_schedule(client_sdr_id)

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


@CLIENT_BLUEPRINT.route("/archetype/<int:archetype_id>/deactivate", methods=["POST"])
@require_user
def post_deactivate_archetype(client_sdr_id: int, archetype_id: int):
    hard_deactivate = get_request_parameter(
        "hard_deactivate", request, json=True, required=True, parameter_type=bool
    )

    if hard_deactivate:
        success = hard_deactivate_client_archetype(
            client_sdr_id=client_sdr_id, client_archetype_id=archetype_id
        )
        if success:
            return (
                jsonify(
                    {
                        "status": "success",
                        "data": {"message": "Deactivated and cleared messages"},
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Failed to deactivate and clear messages",
                    }
                ),
                404,
            )
    else:
        success = deactivate_client_archetype(
            client_sdr_id=client_sdr_id, client_archetype_id=archetype_id
        )
        if success:
            return (
                jsonify({"status": "success", "data": {"message": "Deactivated"}}),
                200,
            )
        else:
            return jsonify({"status": "error", "message": "Failed to deactivate"}), 404


@CLIENT_BLUEPRINT.route("/archetype/<int:archetype_id>/activate", methods=["POST"])
@require_user
def post_activate_archetype(client_sdr_id: int, archetype_id: int):
    success = activate_client_archetype(
        client_sdr_id=client_sdr_id, client_archetype_id=archetype_id
    )
    if success:
        return jsonify({"status": "success", "data": {"message": "Activated"}}), 200

    return jsonify({"status": "error", "message": "Failed to activate"}), 404


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


@CLIENT_BLUEPRINT.route("/sdr/webhook", methods=["PATCH"])
@require_user
def patch_client_sdr_webhook(client_sdr_id):
    """Update the Client SDR Webhook"""
    webhook = get_request_parameter("webhook", request, json=True, required=True)

    success = update_client_sdr_pipeline_notification_webhook(
        client_sdr_id=client_sdr_id, webhook=webhook
    )

    if not success:
        return jsonify({"status": "error", "message": "Failed to update webhook"}), 404
    return jsonify({"status": "success", "message": "Webhook updated"}), 200


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


@CLIENT_BLUEPRINT.route("/webhook", methods=["PATCH"])
@require_user
def patch_client_webhook(client_sdr_id):
    """Update the Client Webhook"""
    webhook = get_request_parameter("webhook", request, json=True, required=True)

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    success = update_client_pipeline_notification_webhook(
        client_id=sdr.client_id, webhook=webhook
    )

    if not success:
        return jsonify({"status": "error", "message": "Failed to update webhook"}), 404
    return jsonify({"status": "success", "message": "Webhook updated"}), 200


@CLIENT_BLUEPRINT.route("/test_webhook", methods=["POST"])
@require_user
def post_test_client_webhook(client_sdr_id):
    """Sends a test message through the Client Webhook

    Returns:
        response.status_code: 200 if successful, 404 if not
    """

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    success = test_client_pipeline_notification_webhook(client_id=sdr.client_id)

    if not success:
        return "Failed to test pipeline client webhook", 404
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


# @CLIENT_BLUEPRINT.route("/sdr/update_weekly_li_outbound_target", methods=["PATCH"])
# def patch_update_sdr_weekly_li_outbound_target():
#     client_sdr_id: int = get_request_parameter(
#         "client_sdr_id", request, json=True, required=True
#     )
#     weekly_li_outbound_target: int = get_request_parameter(
#         "weekly_li_outbound_target", request, json=True, required=True
#     )
#     success = update_client_sdr_weekly_li_outbound_target(
#         client_sdr_id=client_sdr_id, weekly_li_outbound_target=weekly_li_outbound_target
#     )
#     if not success:
#         return "Failed to update weekly LI outbound target", 400
#     return "OK", 200


# @CLIENT_BLUEPRINT.route("/sdr/update_weekly_email_outbound_target", methods=["PATCH"])
# def patch_update_sdr_weekly_email_outbound_target():
#     client_sdr_id: int = get_request_parameter(
#         "client_sdr_id", request, json=True, required=True
#     )
#     weekly_email_outbound_target: int = get_request_parameter(
#         "weekly_email_outbound_target", request, json=True, required=True
#     )
#     success = update_client_sdr_weekly_email_outbound_target(
#         client_sdr_id=client_sdr_id,
#         weekly_email_outbound_target=weekly_email_outbound_target,
#     )
#     if not success:
#         return "Failed to update weekly email outbound target", 400
#     return "OK", 200


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


@CLIENT_BLUEPRINT.route(
    "/archetype/set_transformer_blocklist_initial", methods=["POST"]
)
def post_archetype_set_transformer_blocklist_initial():
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    new_blocklist: list = get_request_parameter(
        "new_blocklist", request, json=True, required=True
    )

    success, message = update_transformer_blocklist_initial(
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


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>/prospect_filter", methods=["GET"])
@require_user
def get_prospect_filter(client_sdr_id: int, archetype_id: int):
    """Gets prospect filter for an archetype"""

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return "Archetype not found or not owned by client SDR", 404

    filters = archetype.prospect_filters
    if filters is None:
        create_empty_archetype_prospect_filters(client_sdr_id, archetype_id)
        archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
        filters = archetype.prospect_filters

    return jsonify({"message": "success", "data": filters}), 200


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>/prospect_filter", methods=["PATCH"])
@require_user
def patch_prospect_filter(client_sdr_id: int, archetype_id: int):
    """Modify prospect filter for an archetype"""
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return "Client SDR not found", 404

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return "Archetype not found or not owned by client SDR", 404

    current_company_names_inclusion = (
        get_request_parameter(
            "current_company_names_inclusion", request, json=True, required=False
        )
        or []
    )
    current_company_names_exclusion = (
        get_request_parameter(
            "current_company_names_exclusion", request, json=True, required=False
        )
        or []
    )
    past_company_names_inclusion = (
        get_request_parameter(
            "past_company_names_inclusion", request, json=True, required=False
        )
        or []
    )
    past_company_names_exclusion = (
        get_request_parameter(
            "past_company_names_exclusion", request, json=True, required=False
        )
        or []
    )
    current_job_title_inclusion = (
        get_request_parameter(
            "current_job_title_inclusion", request, json=True, required=False
        )
        or []
    )
    current_job_title_exclusion = (
        get_request_parameter(
            "current_job_title_exclusion", request, json=True, required=False
        )
        or []
    )
    past_job_title_inclusion = (
        get_request_parameter(
            "past_job_title_inclusion", request, json=True, required=False
        )
        or []
    )
    past_job_title_exclusion = (
        get_request_parameter(
            "past_job_title_exclusion", request, json=True, required=False
        )
        or []
    )
    current_job_function_inclusion = (
        get_request_parameter(
            "current_job_function_inclusion", request, json=True, required=False
        )
        or []
    )
    current_job_function_exclusion = (
        get_request_parameter(
            "current_job_function_exclusion", request, json=True, required=False
        )
        or []
    )
    seniority_inclusion = (
        get_request_parameter("seniority_inclusion", request, json=True, required=False)
        or []
    )
    seniority_exclusion = (
        get_request_parameter("seniority_exclusion", request, json=True, required=False)
        or []
    )
    years_in_current_company = (
        get_request_parameter(
            "years_in_current_company", request, json=True, required=False
        )
        or []
    )
    years_in_current_position = (
        get_request_parameter(
            "years_in_current_position", request, json=True, required=False
        )
        or []
    )
    geography_inclusion = (
        get_request_parameter("geography_inclusion", request, json=True, required=False)
        or []
    )
    geography_exclusion = (
        get_request_parameter("geography_exclusion", request, json=True, required=False)
        or []
    )
    industry_inclusion = (
        get_request_parameter("industry_inclusion", request, json=True, required=False)
        or []
    )
    industry_exclusion = (
        get_request_parameter("industry_exclusion", request, json=True, required=False)
        or []
    )
    years_of_experience = (
        get_request_parameter("years_of_experience", request, json=True, required=False)
        or []
    )
    annual_revenue = (
        get_request_parameter("annual_revenue", request, json=True, required=False)
        or []
    )
    headcount = (
        get_request_parameter("headcount", request, json=True, required=False) or []
    )
    headquarter_location_inclusion = (
        get_request_parameter(
            "headquarter_location_inclusion", request, json=True, required=False
        )
        or []
    )
    headquarter_location_exclusion = (
        get_request_parameter(
            "headquarter_location_exclusion", request, json=True, required=False
        )
        or []
    )
    account_industry_inclusion = (
        get_request_parameter(
            "account_industry_inclusion", request, json=True, required=False
        )
        or []
    )
    account_industry_exclusion = (
        get_request_parameter(
            "account_industry_exclusion", request, json=True, required=False
        )
        or []
    )

    result = modify_archetype_prospect_filters(
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        current_company_names_inclusion=current_company_names_inclusion,
        current_company_names_exclusion=current_company_names_exclusion,
        past_company_names_inclusion=past_company_names_inclusion,
        past_company_names_exclusion=past_company_names_exclusion,
        current_job_title_inclusion=current_job_title_inclusion,
        current_job_title_exclusion=current_job_title_exclusion,
        past_job_title_inclusion=past_job_title_inclusion,
        past_job_title_exclusion=past_job_title_exclusion,
        current_job_function_inclusion=current_job_function_inclusion,
        current_job_function_exclusion=current_job_function_exclusion,
        seniority_inclusion=seniority_inclusion,
        seniority_exclusion=seniority_exclusion,
        years_in_current_company=years_in_current_company,
        years_in_current_position=years_in_current_position,
        geography_inclusion=geography_inclusion,
        geography_exclusion=geography_exclusion,
        industry_inclusion=industry_inclusion,
        industry_exclusion=industry_exclusion,
        years_of_experience=years_of_experience,
        annual_revenue=annual_revenue,
        headcount=headcount,
        headquarter_location_inclusion=headquarter_location_inclusion,
        headquarter_location_exclusion=headquarter_location_exclusion,
        account_industry_inclusion=account_industry_inclusion,
        account_industry_exclusion=account_industry_exclusion,
    )

    if not result:
        return (
            jsonify(
                {"status": "Error", "message": "Failed to apply new prospect filters"}
            ),
            400,
        )

    return (
        jsonify(
            {
                "status": "Success",
                "message": "Successfully applied new prospect filters",
            }
        ),
        200,
    )


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


@CLIENT_BLUEPRINT.route("/sdr/toggle_auto_bump", methods=["POST"])
def post_toggle_client_sdr_auto_bump():
    """Toggles auto bump for a client SDR"""
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    success = toggle_client_sdr_auto_bump(client_sdr_id=client_sdr_id)
    if not success:
        return "Failed to toggle auto bump", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/toggle_auto_send_linkedin_campaign", methods=["POST"])
@require_user
def post_toggle_client_sdr_auto_send_linkedin_campaigns(client_sdr_id: int):
    """Toggles auto send campaigns enabled for a client SDR"""

    success = toggle_client_sdr_auto_send_linkedin_campaign(client_sdr_id=client_sdr_id)
    if not success:
        return "Failed to toggle auto send campaigns enabled", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/toggle_auto_send_email_campaign", methods=["POST"])
@require_user
def post_toggle_client_sdr_auto_send_email_campaigns(client_sdr_id: int):
    """Toggles auto send campaigns enabled for a client SDR"""
    enabled = get_request_parameter(
        "enabled", request, json=True, required=True, parameter_type=bool
    )

    success = toggle_client_sdr_auto_send_email_campaign(
        client_sdr_id=client_sdr_id,
        enabled=enabled,
    )
    if not success:
        return "Failed to toggle auto send campaigns enabled", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/auto_bump", methods=["POST"])
@require_user
def post_client_sdr_auto_bump(client_sdr_id: int):
    """Toggles auto bump for a client SDR"""
    success = toggle_client_sdr_auto_bump(client_sdr_id=client_sdr_id)
    if not success:
        return (
            jsonify({"status": "error", "message": "Failed to toggle auto bump"}),
            400,
        )
    return jsonify({"status": "success", "data": {}}), 200


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
        "client_pod_id", request, json=True, required=False
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


@CLIENT_BLUEPRINT.route("/sdr/find_events", methods=["GET"])
@require_user
def get_prospect_events(client_sdr_id: int):
    """Finds all calendar events for a prospect"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=False, parameter_type=int
    )

    if prospect_id:
        events = find_prospect_events(client_sdr_id, prospect_id)
    else:
        events = [e.to_dict() for e in find_sdr_events(client_sdr_id)]

    if events is None:
        return jsonify({"message": "Failed to find event"}), 404

    return jsonify({"message": "Success", "data": events}), 200


@CLIENT_BLUEPRINT.route("/sdr/find_event", methods=["GET"])
@require_user
def get_prospect_event(client_sdr_id: int):
    """Finds a calendar event"""

    event_id = get_request_parameter(
        "event_id", request, json=False, required=True, parameter_type=str
    )

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    success = populate_single_prospect_event(sdr.nylas_account_id, event_id)

    if not success:
        return jsonify({"message": "Failed to find event"}), 404

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sdr/populate_events", methods=["POST"])
@require_user
def post_populate_prospect_events(client_sdr_id: int):
    """Populates the db with the prospect's calendar events"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    added_count, updated_count = populate_prospect_events(client_sdr_id, prospect_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": {
                    "added": added_count,
                    "updated": updated_count,
                },
            }
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/sdr/calendar_availability", methods=["GET"])
@require_user
def get_calendar_availability(client_sdr_id: int):
    """Gets the calendar availability for an SDR"""

    start_time = get_request_parameter(
        "start_time", request, json=False, required=True, parameter_type=int
    )
    end_time = get_request_parameter(
        "end_time", request, json=False, required=True, parameter_type=int
    )

    return get_sdr_calendar_availability(client_sdr_id, start_time, end_time)


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
    "/archetype/<archetype_id>/email_blocks",
    defaults={"email_bump_framework_id": None},
    methods=["GET"],
)
@CLIENT_BLUEPRINT.route(
    "/archetype/<archetype_id>/email_blocks/<email_bump_framework_id>", methods=["GET"]
)
@require_user
def get_email_blocks(
    client_sdr_id: int, archetype_id: int, email_bump_framework_id: Optional[int]
):
    """Gets email blocks for an archetype"""
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not sdr or not archetype:
        return (
            jsonify({"status": "error", "message": "SDR or Archetype not found"}),
            404,
        )
    if archetype.client_sdr_id != sdr.id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "SDR does not have access to this archetype",
                }
            ),
            403,
        )

    email_blocks = get_email_blocks_configuration(
        client_sdr_id, archetype_id, email_bump_framework_id
    )

    return jsonify({"status": "success", "data": email_blocks}), 200


@CLIENT_BLUEPRINT.route("/archetype/<archetype_id>/email_blocks", methods=["PATCH"])
@require_user
def patch_email_blocks(client_sdr_id: int, archetype_id: int):
    """Updates email blocks for an archetype"""
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not sdr or not archetype:
        return (
            jsonify({"status": "error", "message": "SDR or Archetype not found"}),
            404,
        )
    if archetype.client_sdr_id != sdr.id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "SDR does not have access to this archetype",
                }
            ),
            403,
        )

    email_blocks = (
        get_request_parameter("email_blocks", request, json=True, required=True) or []
    )

    patch_archetype_email_blocks_configuration(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        blocks=email_blocks,
    )

    return jsonify({"status": "success"}), 200


@CLIENT_BLUEPRINT.route(
    "/archetype/<archetype_id>/update_description_and_fit", methods=["POST"]
)
@require_user
def post_update_persona_details(client_sdr_id: int, archetype_id: int):
    """Updates the description and fit for an archetype"""
    updated_persona_name = get_request_parameter(
        "updated_persona_name", request, json=True, required=False
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
    updated_persona_contract_size = get_request_parameter(
        "updated_persona_contract_size", request, json=True, required=False
    )
    updated_cta_framework_company = get_request_parameter(
        "updated_cta_framework_company", request, json=True, required=False
    )
    updated_cta_framework_persona = get_request_parameter(
        "updated_cta_framework_persona", request, json=True, required=False
    )
    updated_cta_framework_action = get_request_parameter(
        "updated_cta_framework_action", request, json=True, required=False
    )
    updated_use_cases = get_request_parameter(
        "updated_use_cases", request, json=True, required=False
    )
    updated_filters = get_request_parameter(
        "updated_filters", request, json=True, required=False
    )
    updated_lookalike_profile_1 = get_request_parameter(
        "updated_lookalike_profile_1", request, json=True, required=False
    )
    updated_lookalike_profile_2 = get_request_parameter(
        "updated_lookalike_profile_2", request, json=True, required=False
    )
    updated_lookalike_profile_3 = get_request_parameter(
        "updated_lookalike_profile_3", request, json=True, required=False
    )
    updated_lookalike_profile_4 = get_request_parameter(
        "updated_lookalike_profile_4", request, json=True, required=False
    )
    updated_lookalike_profile_5 = get_request_parameter(
        "updated_lookalike_profile_5", request, json=True, required=False
    )

    success = update_persona_brain_details(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        updated_persona_name=updated_persona_name,
        updated_persona_fit_reason=updated_persona_fit_reason,
        updated_persona_icp_matching_prompt=updated_persona_icp_matching_prompt,
        updated_persona_contact_objective=updated_persona_contact_objective,
        updated_persona_contract_size=updated_persona_contract_size,
        updated_cta_framework_company=updated_cta_framework_company,
        updated_cta_framework_persona=updated_cta_framework_persona,
        updated_cta_framework_action=updated_cta_framework_action,
        updated_use_cases=updated_use_cases,
        updated_filters=updated_filters,
        updated_lookalike_profile_1=updated_lookalike_profile_1,
        updated_lookalike_profile_2=updated_lookalike_profile_2,
        updated_lookalike_profile_3=updated_lookalike_profile_3,
        updated_lookalike_profile_4=updated_lookalike_profile_4,
        updated_lookalike_profile_5=updated_lookalike_profile_5,
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
    persona_buy_reason = get_request_parameter(
        "persona_buy_reason", request, json=True, required=False
    )
    message = generate_persona_icp_matching_prompt(
        client_sdr_id=client_sdr_id,
        persona_name=persona_name,
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
    next_demo_date = get_request_parameter(
        "next_demo_date", request, json=True, required=False, parameter_type=str
    )
    ai_adjustments = get_request_parameter(
        "ai_adjustments", request, json=True, required=False, parameter_type=str
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect not found"}), 400

    result = submit_demo_feedback(
        client_id=client_sdr.client_id,
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        status=status,
        rating=rating,
        feedback=feedback,
        next_demo_date=next_demo_date,
        ai_adjustments=ai_adjustments,
    )

    # Send the Slack Notification
    success = create_and_send_slack_notification_class_message(
        notification_type=SlackNotificationType.DEMO_FEEDBACK_COLLECTED,
        arguments={
            "client_sdr_id": client_sdr_id,
            "prospect_id": prospect_id,
            "rating": rating,
            "notes": feedback,
            "demo_status": status,
        },
    )

    # notification = DemoFeedbackCollectedNotification(
    #     client_sdr_id=client_sdr.id,
    #     prospect_id=prospect_id,
    #     rating=rating,
    #     notes=feedback,
    #     demo_status=status,
    # )
    # notification.send_notification(preview_mode=False)

    # REMOVE THIS CODE
    # direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
    #     auth_token=client_sdr.auth_token,
    #     prospect_id=prospect.id,
    # )
    # send_slack_message(
    #     message="🎊 ✍️ NEW Demo Feedback Collected",
    #     webhook_urls=[
    #         URL_MAP["csm-demo-feedback"],
    #         client.pipeline_notifications_webhook_url,
    #     ],
    #     blocks=[
    #         {
    #             "type": "header",
    #             "text": {
    #                 "type": "plain_text",
    #                 "text": "🎊 ✍️ NEW Demo Feedback Collected",
    #                 "emoji": True,
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Prospect*: {prospect_name}\n*Rating*: {rating}\n{notes}".format(
    #                     prospect_name=prospect.full_name
    #                     + " ("
    #                     + prospect.company
    #                     + ")",
    #                     rating=rating,
    #                     rep=client_sdr.name,
    #                     notes="*Feedback*: " + feedback if feedback else "",
    #                 ),
    #             },
    #         },
    #         {"type": "divider"},
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Rep*: {rep}".format(rep=client_sdr.name),
    #             },
    #             "accessory": {
    #                 "type": "button",
    #                 "text": {
    #                     "type": "plain_text",
    #                     "text": "View Convo in Sight",
    #                     "emoji": True,
    #                 },
    #                 "value": direct_link,
    #                 "url": direct_link,
    #                 "action_id": "button-action",
    #             },
    #         },
    #     ],
    # )

    if ai_adjustments:
        send_slack_message(
            message="✨ AI is retargeting based on demo feedback",
            webhook_urls=[
                URL_MAP["csm-demo-feedback"],
                client.pipeline_notifications_webhook_url,
            ],
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "✨ AI is retargeting based on demo feedback",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Notes*:\n> {ai_adjustments}".format(
                            ai_adjustments=ai_adjustments
                        ),
                    },
                },
            ],
        )

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/demo_feedback", methods=["GET"])
@require_user
def get_demo_feedback_sdr_endpoint(client_sdr_id: int):
    """Get demo feedback"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=False
    )

    if prospect_id:
        list_of_feedback = get_demo_feedback(client_sdr_id, prospect_id)

        if not list_of_feedback:
            return jsonify({"message": "Feedback not found"}), 400

        return (
            jsonify(
                {
                    "message": "Success",
                    "data": [feedback.to_dict() for feedback in list_of_feedback],
                }
            ),
            200,
        )

    else:
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


@CLIENT_BLUEPRINT.route("/demo_feedback", methods=["PATCH"])
@require_user
def patch_demo_feedback(client_sdr_id: int):
    """Patch demo feedback"""

    feedback_id = get_request_parameter(
        "feedback_id", request, json=True, required=True, parameter_type=int
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
    ai_adjustments = get_request_parameter(
        "ai_adjustments", request, json=True, required=False, parameter_type=str
    )
    next_demo_date = get_request_parameter(
        "next_demo_date", request, json=True, required=False, parameter_type=str
    )

    df: DemoFeedback = DemoFeedback.query.get(feedback_id)
    if df.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Feedback does not belong to you"}),
            403,
        )

    result = edit_demo_feedback(
        client_sdr_id=client_sdr_id,
        demo_feedback_id=feedback_id,
        status=status,
        rating=rating,
        feedback=feedback,
        next_demo_date=next_demo_date,
        ai_adjustments=ai_adjustments,
    )
    if not result:
        return (
            jsonify(
                {"status": "error", "message": "Demo feedback could not be edited"}
            ),
            400,
        )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(df.prospect_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    # Send the Slack Notification
    success = create_and_send_slack_notification_class_message(
        notification_type=SlackNotificationType.DEMO_FEEDBACK_UPDATED,
        arguments={
            "client_sdr_id": client_sdr_id,
            "prospect_id": prospect.id,
            "rating": rating,
            "notes": feedback,
            "demo_status": status,
            "ai_adjustment": ai_adjustments,
        },
    )

    # updated_feedback_notification = DemoFeedbackUpdatedNotification(
    #     client_sdr_id=client_sdr.id,
    #     prospect_id=prospect.id,
    #     rating=rating,
    #     notes=feedback,
    #     demo_status=status,
    #     ai_adjustment=ai_adjustments,
    # )
    # updated_feedback_notification.send_notification(preview_mode=False)

    # send_slack_message(
    #     message="🎊 ✍️ UPDATED Demo Feedback",
    #     webhook_urls=[
    #         URL_MAP["csm-demo-feedback"],
    #         client.pipeline_notifications_webhook_url,
    #     ],
    #     blocks=[
    #         {
    #             "type": "header",
    #             "text": {
    #                 "type": "plain_text",
    #                 "text": "🎊 ✍️ UPDATED Demo Feedback",
    #                 "emoji": True,
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Rep*: {rep}\n*Rating*: {rating}\n*Notes*: {notes}\n*AI Adjustments*: {ai_adjustments}".format(
    #                     rating=rating,
    #                     rep=client_sdr.name,
    #                     notes=feedback,
    #                     ai_adjustments=ai_adjustments,
    #                 ),
    #             },
    #         },
    #         {"type": "divider"},
    #         {
    #             "type": "context",
    #             "elements": [
    #                 {
    #                     "type": "mrkdwn",
    #                     "text": "*Prospect*: {prospect}\n*Company*: {company}\n*Persona*: {persona}\n*Date of demo*: {date}\n*Demo*: {showed}".format(
    #                         prospect=prospect.full_name,
    #                         company=prospect.company,
    #                         persona=archetype.archetype,
    #                         date=str(prospect.demo_date),
    #                         showed=status,
    #                     ),
    #                 }
    #             ],
    #         },
    #     ],
    # )

    return jsonify({"status": "success", "data": {"message": "Success"}}), 200


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
    do_not_contact_industries = get_request_parameter(
        "do_not_contact_industries", request, json=True, required=False
    )
    do_not_contact_location_keywords = get_request_parameter(
        "do_not_contact_location_keywords", request, json=True, required=False
    )
    do_not_contact_titles = get_request_parameter(
        "do_not_contact_titles", request, json=True, required=False
    )
    do_not_contact_prospect_location_keywords = get_request_parameter(
        "do_not_contact_prospect_location_keywords",
        request,
        json=True,
        required=False,
    )
    do_not_contact_people_names = get_request_parameter(
        "do_not_contact_people_names", request, json=True, required=False
    )
    do_not_contact_emails = get_request_parameter(
        "do_not_contact_emails", request, json=True, required=False
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    success = update_do_not_contact_filters(
        client_id=client_id,
        do_not_contact_keywords_in_company_names=do_not_contact_keywords_in_company_names,
        do_not_contact_company_names=do_not_contact_company_names,
        do_not_contact_industries=do_not_contact_industries,
        do_not_contact_location_keywords=do_not_contact_location_keywords,
        do_not_contact_titles=do_not_contact_titles,
        do_not_contact_prospect_location_keywords=do_not_contact_prospect_location_keywords,
        do_not_contact_people_names=do_not_contact_people_names,
        do_not_contact_emails=do_not_contact_emails,
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


@CLIENT_BLUEPRINT.route("/sdr/do_not_contact_filters", methods=["POST"])
@require_user
def post_sdr_do_not_contact_filters(client_sdr_id: int):
    do_not_contact_keywords_in_company_names = get_request_parameter(
        "do_not_contact_keywords_in_company_names", request, json=True, required=False
    )
    do_not_contact_company_names = get_request_parameter(
        "do_not_contact_company_names", request, json=True, required=False
    )
    do_not_contact_industries = get_request_parameter(
        "do_not_contact_industries", request, json=True, required=False
    )
    do_not_contact_location_keywords = get_request_parameter(
        "do_not_contact_location_keywords", request, json=True, required=False
    )
    do_not_contact_titles = get_request_parameter(
        "do_not_contact_titles", request, json=True, required=False
    )
    do_not_contact_prospect_location_keywords = get_request_parameter(
        "do_not_contact_prospect_location_keywords",
        request,
        json=True,
        required=False,
    )
    do_not_contact_people_names = get_request_parameter(
        "do_not_contact_people_names", request, json=True, required=False
    )
    do_not_contact_emails = get_request_parameter(
        "do_not_contact_emails", request, json=True, required=False
    )

    success = update_sdr_do_not_contact_filters(
        client_sdr_id=client_sdr_id,
        do_not_contact_keywords_in_company_names=do_not_contact_keywords_in_company_names,
        do_not_contact_company_names=do_not_contact_company_names,
        do_not_contact_industries=do_not_contact_industries,
        do_not_contact_location_keywords=do_not_contact_location_keywords,
        do_not_contact_titles=do_not_contact_titles,
        do_not_contact_prospect_location_keywords=do_not_contact_prospect_location_keywords,
        do_not_contact_people_names=do_not_contact_people_names,
        do_not_contact_emails=do_not_contact_emails,
    )
    if not success:
        return "Failed to update do not contact filters", 400

    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/do_not_contact_filters", methods=["GET"])
@require_user
def get_sdr_do_not_contact_filters_endpoint(client_sdr_id: int):
    data = get_sdr_do_not_contact_filters(
        client_sdr_id=client_sdr_id,
    )
    return jsonify({"data": data}), 200


@CLIENT_BLUEPRINT.route("/sdr/do_not_contact_filters/caught_prospects", methods=["GET"])
@require_user
def get_sdr_caught_prospects_endpoint(client_sdr_id: int):
    prospects = list_prospects_caught_by_sdr_client_filters(
        client_sdr_id=client_sdr_id,
    )
    return jsonify({"prospects": prospects}), 200


@CLIENT_BLUEPRINT.route(
    "/sdr/do_not_contact_filters/remove_prospects", methods=["POST"]
)
@require_user
def post_sdr_remove_prospects_endpoint(client_sdr_id: int):
    """Removes prospects from the do not contact filters"""
    success = remove_prospects_caught_by_sdr_client_filters(
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


@CLIENT_BLUEPRINT.route("/demo_feedback_feed", methods=["GET"])
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


@CLIENT_BLUEPRINT.route("/update_super_sight_link", methods=["POST"])
def post_update_supersight_link():
    client_id: int = get_request_parameter(
        "client_id", request, json=True, required=True
    )
    super_sight_link: str = get_request_parameter(
        "super_sight_link", request, json=True, required=True
    )
    success = update_client_sdr_supersight_link(
        client_id=client_id, super_sight_link=super_sight_link
    )
    if not success:
        return "Failed to update supersight link", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/onboarding_completion_report", methods=["GET"])
@require_user
def get_onboarding_completion_report(client_sdr_id: int):
    """Gets the onboarding completion report for an SDR"""

    report = onboarding_setup_completion_report(client_sdr_id)

    return jsonify({"message": "Success", "data": report}), 200


@CLIENT_BLUEPRINT.route("/persona/setup_status/<int:persona_id>", methods=["GET"])
@require_user
def get_persona_setup_status(client_sdr_id: int, persona_id: int):
    """Gets the setup status for a persona"""

    persona: ClientArchetype = ClientArchetype.query.get(persona_id)
    if not persona or persona.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Invalid persona"}), 400

    status = get_persona_setup_status_map_for_persona(persona_id)
    return jsonify({"message": "Success", "data": status}), 200


@CLIENT_BLUEPRINT.route("/sdr/blacklist_words", methods=["PATCH"])
@require_user
def patch_sdr_blacklist_words(client_sdr_id: int):
    """Updates the blacklist words for an SDR"""

    blacklist_words = get_request_parameter(
        "blacklist_words", request, json=True, required=True
    )

    success = update_sdr_blacklist_words(client_sdr_id, blacklist_words)

    if not success:
        return jsonify({"message": "Failed to update blacklist words"}), 400

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/persona/update_emoji", methods=["POST"])
@require_user
def post_update_persona_emoji(client_sdr_id: int):
    """Updates the emoji for a persona"""

    persona_id = get_request_parameter("persona_id", request, json=True, required=True)
    emoji = get_request_parameter("emoji", request, json=True, required=True)

    persona: ClientArchetype = ClientArchetype.query.get(persona_id)
    if not persona or client_sdr_id != persona.client_sdr_id:
        return "Unauthorized or persona not found", 403

    success = update_archetype_emoji(persona_id, emoji)

    if not success:
        return jsonify({"message": "Failed to update persona emoji"}), 400

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/pre_onboarding_survey", methods=["GET"])
@require_user
def get_pre_onboarding_survey(client_sdr_id: int):
    """Gets the pre onboarding survey for an SDR"""

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return jsonify({"message": "Invalid SDR"}), 400

    client: Client = Client.query.get(client_sdr.client_id)
    if not client:
        return jsonify({"message": "Invalid Client"}), 400

    pre_onboarding_survey = client.pre_onboarding_survey or {}

    return jsonify(pre_onboarding_survey), 200


@CLIENT_BLUEPRINT.route("/pre_onboarding_survey", methods=["POST"])
@require_user
def post_pre_onboarding_survey(client_sdr_id: int):
    """Writes a key value pair to the pre onboarding survey for a client"""

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return jsonify({"message": "Invalid SDR"}), 400

    key = get_request_parameter("key", request, json=True, required=True)
    value = get_request_parameter("value", request, json=True, required=True)

    success = write_client_pre_onboarding_survey(
        client_sdr_id=client_sdr_id,
        client_id=client_sdr.client_id,
        key=key,
        value=value,
    )
    if not success:
        return jsonify({"message": "Failed to write to pre onboarding survey"}), 400

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/sync_pre_onboarding_data", methods=["POST"])
@require_user
def post_sync_pre_onboarding_data(client_sdr_id: int):
    """Syncs pre onboarding data from client to client sdr"""

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return jsonify({"message": "Invalid SDR"}), 400

    success, message = import_pre_onboarding(client_sdr_id)

    if not success:
        return jsonify({"message": message}), 400

    return jsonify({"message": "Success"}), 200


@CLIENT_BLUEPRINT.route("/update_bcc_cc_emails", methods=["POST"])
@require_user
def post_update_bcc_cc_emails(client_sdr_id: int):
    cc_emails = get_request_parameter("cc_emails", request, json=True, required=False)
    bcc_emails = get_request_parameter("bcc_emails", request, json=True, required=False)

    success = update_client_sdr_cc_bcc_emails(
        client_sdr_id=client_sdr_id,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
    )

    if not success:
        return "Failed to update cc and bcc emails", 400

    return "OK", 200


@CLIENT_BLUEPRINT.route("/tam_graph_data", methods=["GET"])
@require_user
def get_tam_graph_data(client_sdr_id: int):
    results = get_tam_data(
        client_sdr_id=client_sdr_id,
    )

    return jsonify({"message": "Success", "data": results}), 200


@CLIENT_BLUEPRINT.route("/campaign_overview", methods=["GET"])
@require_user
def get_campaign_overview(client_sdr_id: int):
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Unauthorized or persona not found", 403

    overview = get_client_archetype_stats(
        client_archetype_id=client_archetype_id,
    )

    return jsonify(overview), 200


@CLIENT_BLUEPRINT.route("/campaign_stats", methods=["GET"])
@require_user
def get_campaign_stats(client_sdr_id: int):
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Unauthorized or persona not found", 403

    overview = get_client_archetype_overview(
        client_archetype_id=client_archetype_id,
    )

    return jsonify(overview), 200

@CLIENT_BLUEPRINT.route("/upload_in_progres", methods=["GET"])
@require_user
def get_upload_in_progress(client_sdr_id: int):
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Unauthorized or persona not found", 403

    upload_in_progress = is_archetype_uploading_contacts(client_archetype_id=client_archetype_id)
    return jsonify({"upload_in_progress": bool(upload_in_progress)}), 200

@CLIENT_BLUEPRINT.route("/campaign_contacts", methods=["GET"])
@require_user
def get_campaign_contacts(client_sdr_id: int):
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    offset: int = get_request_parameter(
        "offset", request, json=False, required=False, parameter_type=str
    )
    limit: int = get_request_parameter(
        "limit", request, json=False, required=False, parameter_type=str
    )
    text: str = get_request_parameter(
        "text", request, json=False, required=False, parameter_type=str
    )

    include_analytics: str = get_request_parameter(
        "include_analytics", request, json=False, required=False, parameter_type=str
    )
    
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Unauthorized or persona not found", 403

    contacts = get_client_archetype_contacts(client_archetype_id, int(offset), int(limit), text, include_analytics=include_analytics)
    return jsonify(contacts), 200

@CLIENT_BLUEPRINT.route("/total_contacts", methods=["GET"])
@require_user
def get_total_contacts(client_sdr_id: int):
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Unauthorized or persona not found", 403

    total_contacts = get_total_contacts_for_archetype(client_archetype_id)
    return jsonify({"total_contacts": total_contacts}), 200

@CLIENT_BLUEPRINT.route("/campaign_sequences", methods=["GET"])
@require_user
def get_campaign_sequences(client_sdr_id: int):
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Unauthorized or persona not found", 403

    sequences = get_client_archetype_sequences(client_archetype_id)
    return jsonify(sequences), 200

@CLIENT_BLUEPRINT.route("/campaign_analytics", methods=["GET"])
@require_user
def get_campaign_analytics(client_sdr_id: int):
    client_archetype_id: int = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    if not ca or ca.client_sdr_id != client_sdr_id:
        return "Unauthorized or persona not found", 403

    analytics = get_client_archetype_analytics(client_archetype_id)
    return jsonify(analytics), 200

@CLIENT_BLUEPRINT.route("/sent_volume_during_period", methods=["POST"])
@require_user
def get_sent_volume_during_period(client_sdr_id: int):
    data = request.get_json()
    start_date = data.get("start_date")
    campaign_id = data.get("campaign_id")
    end_date = data.get("end_date")

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required"}), 400

    try:
        sent_emails_count = get_sent_volume_during_time_period(client_sdr_id, start_date, end_date, campaign_id)
        return jsonify({"sent_emails_count": sent_emails_count}), 200
    except Exception as e:
        return jsonify({"error": "Internal Server Error"}), 500

@CLIENT_BLUEPRINT.route("/send_generic_email", methods=["POST"])
@require_user
def post_send_generic_email(client_sdr_id: int):
    from_email = get_request_parameter("from_email", request, json=True, required=True)
    to_emails = get_request_parameter("to_emails", request, json=True, required=True)
    bcc_emails = get_request_parameter("bcc_emails", request, json=True, required=True)
    subject = get_request_parameter("subject", request, json=True, required=True)
    body = get_request_parameter("body", request, json=True, required=True)

    send_email(
        html=body,
        title=subject,
        from_email=from_email,
        to_emails=to_emails,
        bcc_emails=bcc_emails,
    )

    return jsonify({"message": "Success", "data": True}), 200


@CLIENT_BLUEPRINT.route("/msg_analytics_report", methods=["GET"])
@require_user
def get_msg_analytics_report(client_sdr_id: int):
    results = msg_analytics_report(client_sdr_id)

    return jsonify({"message": "Success", "data": results}), 200


@CLIENT_BLUEPRINT.route("/ask_ae_notifs", methods=["POST"])
@require_user
def post_ask_ae_notifs(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    question = get_request_parameter(
        "question", request, json=True, required=True, parameter_type=str
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    prospect_note_id = create_note(
        prospect_id=prospect_id, note=f"Ask the rep. {question}"
    )

    send_slack_message(
        message=f"SellScale AI is requesting more info from {prospect.full_name}!",
        webhook_urls=[
            URL_MAP["eng-sandbox"],
            client.pipeline_notifications_webhook_url,
        ],
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"SellScale AI is requesting more info from {prospect.full_name}!",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question:* {question}\n\n",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Contact: {client_sdr.name} | Prospect State: {prospect.overall_status}",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Convo in Sight",
                        "emoji": True,
                    },
                    "value": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                        auth_token=client_sdr.auth_token, prospect_id=prospect_id
                    )
                    + str(prospect_id),
                    "url": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                        auth_token=client_sdr.auth_token, prospect_id=prospect_id
                    ),
                    "action_id": "button-action",
                },
            },
        ],
    )

    return jsonify({"message": "Success", "data": True}), 200


@CLIENT_BLUEPRINT.route("/ai_available_times", methods=["POST"])
@require_user
def post_ai_available_times(client_sdr_id: int):
    calendar_url = get_request_parameter(
        "calendar_url", request, json=True, required=True, parameter_type=str
    )
    date = get_request_parameter(
        "date", request, json=True, required=True, parameter_type=str
    )

    available_start_hour = get_request_parameter(
        "available_start_hour", request, json=True, required=False, parameter_type=int
    )
    available_end_hour = get_request_parameter(
        "available_end_hour", request, json=True, required=False, parameter_type=int
    )
    within_next_days = get_request_parameter(
        "within_next_days", request, json=True, required=False, parameter_type=int
    )

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    result = get_available_times_via_calendly(
        calendly_url=calendar_url,
        dt=datetime.strptime(date, "%Y-%m-%d"),
        tz=sdr.timezone,
        start_time=available_start_hour,
        end_time=available_end_hour,
        max_days=within_next_days,
    )

    return jsonify({"message": "Success", "data": result}), 200


@CLIENT_BLUEPRINT.route("/territory_name", methods=["POST"])
@require_user
def post_territory_name(client_sdr_id: int):
    territory_name = get_request_parameter(
        "territory_name", request, json=True, required=True, parameter_type=str
    )

    success = update_client_sdr_territory_name(client_sdr_id, territory_name)

    if not success:
        return "Failed to update territory name", 400

    return "OK", 200


@CLIENT_BLUEPRINT.route("/create_archetype_asset", methods=["POST"])
@require_user
def post_create_archetype_asset(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client_archetype_ids = get_request_parameter(
        "client_archetype_ids", request, json=True, required=False, parameter_type=list
    )
    asset_key = get_request_parameter(
        "asset_key", request, json=True, required=True, parameter_type=str
    )
    asset_value = get_request_parameter(
        "asset_value", request, json=True, required=True, parameter_type=str
    )
    asset_type = get_request_parameter(
        "asset_type", request, json=True, required=False, parameter_type=str
    )
    asset_tags = get_request_parameter(
        "asset_tags", request, json=True, required=False, parameter_type=list
    )
    asset_raw_value = get_request_parameter(
        "asset_raw_value", request, json=True, required=False, parameter_type=str
    )

    asset_dict = create_archetype_asset(
        client_sdr_id=client_sdr_id,
        client_id=client_id,
        client_archetype_ids=client_archetype_ids or [],
        asset_key=asset_key,
        asset_value=asset_value,
        asset_type=asset_type or ClientAssetType.TEXT,
        asset_tags=asset_tags or [],
        asset_raw_value=asset_raw_value or asset_value,
    )

    if not asset_dict:
        return "Failed to create archetype asset", 400

    return jsonify({"message": "Success", "data": asset_dict}), 200


@CLIENT_BLUEPRINT.route("/unrestricted_create_archetype_asset", methods=["POST"])
def post_unrestricted_create_archetype_asset():
    client_id = get_request_parameter(
        "client_id", request, json=True, required=True, parameter_type=int
    )
    persona_id = get_request_parameter(
        "persona_id", request, json=True, required=False, parameter_type=int
    )
    asset_key = get_request_parameter(
        "asset_key", request, json=True, required=True, parameter_type=str
    )
    asset_value = get_request_parameter(
        "asset_value", request, json=True, required=True, parameter_type=str
    )
    asset_type = get_request_parameter(
        "asset_type", request, json=True, required=False, parameter_type=str
    )
    asset_tags = get_request_parameter(
        "asset_tags", request, json=True, required=False, parameter_type=list
    )
    asset_raw_value = get_request_parameter(
        "asset_raw_value", request, json=True, required=False, parameter_type=str
    )

    asset_dict = create_archetype_asset(
        client_sdr_id=None,
        client_id=client_id,
        client_archetype_ids=[],
        asset_key=asset_key,
        asset_value=asset_value,
        asset_type=asset_type or ClientAssetType.TEXT,
        asset_tags=asset_tags or [],
        asset_raw_value=asset_raw_value or asset_value,
    )

    if persona_id and asset_dict:
        link_asset_to_persona(persona_id=persona_id, asset_id=asset_dict.get("id"))

    if not asset_dict:
        return "Failed to create client asset", 400

    return jsonify({"message": "Success", "data": asset_dict}), 200


@CLIENT_BLUEPRINT.route("/get_assets", methods=["GET"])
@require_user
def get_assets_edpoint(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    assets = get_client_assets(client_sdr.client_id)

    return jsonify({"message": "Success", "data": assets}), 200


@CLIENT_BLUEPRINT.route("/asset", methods=["DELETE"])
@require_user
def delete_asset_endpoint(client_sdr_id: int):
    asset_id = get_request_parameter(
        "asset_id", request, json=True, required=True, parameter_type=int
    )
    success = delete_archetype_asset(asset_id, client_sdr_id)
    if not success:
        return "Failed to delete asset", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/toggle_archetype_id_in_asset_ids", methods=["POST"])
@require_user
def post_toggle_archetype_id_in_asset_ids(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )
    asset_id = get_request_parameter(
        "asset_id", request, json=True, required=True, parameter_type=int
    )
    reason = get_request_parameter(
        "reason", request, json=True, required=False, parameter_type=str
    )
    step_number = get_request_parameter(
        "step_number", request, json=True, required=False
    )

    if not reason:
        reason = ""

    asset: ClientAssets = ClientAssets.query.filter_by(
        id=asset_id, client_id=client_id
    ).first()
    if asset.client_archetype_ids and client_archetype_id in asset.client_archetype_ids:
        delete_client_asset_archetype_mapping(client_archetype_id, asset_id)
    else:
        success, message = create_client_archetype_reason_mapping(
            client_archetype_id, asset_id, reason, step_number=step_number
        )
        if not success:
            return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success"}), 200


@CLIENT_BLUEPRINT.route("/asset/reason/<int:reason_id>", methods=["PATCH"])
@require_user
def patch_reason_for_asset(client_sdr_id: int, reason_id: int):
    new_reason = get_request_parameter(
        "reason", request, json=True, required=True, parameter_type=str
    )
    step_number = get_request_parameter(
        "step_number", request, json=True, required=False
    )
    modify_client_archetype_reason_mapping(
        client_asset_archetype_reason_mapping_id=reason_id,
        new_reason=new_reason,
        step_number=step_number,
    )

    return jsonify({"status": "success"}), 200

@CLIENT_BLUEPRINT.route("/archetype/<int:client_archetype_id>/testing_volume", methods=["PATCH"])
@require_user
def patch_testing_volume(client_sdr_id: int, client_archetype_id: int):
    testing_volume = get_request_parameter(
        "testing_volume", request, json=True, required=True, parameter_type=int
    )
    success, message = modify_testing_volume(client_archetype_id, testing_volume)
    if not success:
        return jsonify({"status": "error", "message": message}), 400
    return jsonify({"status": "success", "message": message}), 200

@CLIENT_BLUEPRINT.route("/archetype/<int:client_archetype_id>/testing_volume", methods=["GET"])
@require_user
def get_testing_volume_endpoint(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=False, required=True, parameter_type=int
    )
    testing_volume = get_testing_volume(client_archetype_id)
    return jsonify({"status": "success", "testing_volume": testing_volume}), 200



@CLIENT_BLUEPRINT.route("/update_asset", methods=["POST"])
@require_user
def update_asset_endpoint(client_sdr_id: int):
    asset_id = get_request_parameter(
        "asset_id", request, json=True, required=True, parameter_type=int
    )
    asset_key = get_request_parameter(
        "asset_key", request, json=True, required=False, parameter_type=str
    )
    asset_value = get_request_parameter(
        "asset_value", request, json=True, required=False, parameter_type=str
    )
    asset_type = get_request_parameter(
        "asset_type", request, json=True, required=False, parameter_type=str
    )
    asset_tags = get_request_parameter(
        "asset_tags", request, json=True, required=False, parameter_type=list
    )

    success = update_asset(
        asset_id=asset_id,
        client_sdr_id=client_sdr_id,
        asset_key=asset_key,
        asset_value=asset_value,
        asset_type=asset_type,
        asset_tags=asset_tags,
    )

    if not success:
        return "Failed to update asset", 400
    return "OK", 200


@CLIENT_BLUEPRINT.route("/query_gpt_v", methods=["POST"])
def post_query_gpt_v_endpoint():
    message = get_request_parameter("message", request, json=True, required=True)
    webpage_url = get_request_parameter(
        "webpage_url", request, json=True, required=False, parameter_type=str
    )
    image_url = get_request_parameter(
        "image_url", request, json=True, required=False, parameter_type=str
    )
    max_tokens = get_request_parameter(
        "max_tokens", request, json=True, required=False, parameter_type=int
    )
    image_contents = get_request_parameter(
        "image_contents", request, json=True, required=False, parameter_type=str
    )

    success, response = attempt_chat_completion_with_vision(
        message=message,
        webpage_url=webpage_url,
        image_url=image_url,
        max_tokens=max_tokens,
        image_contents=image_contents,
    )

    return (
        jsonify(
            {"message": "Success", "data": {"success": success, "response": response}}
        ),
        200,
    )


@CLIENT_BLUEPRINT.route("/all_assets_in_client", methods=["GET"])
@require_user
def get_all_assets_in_client(client_sdr_id: int):
    """Gets all assets for a client sdr"""
    assets = fetch_all_assets_in_client(client_sdr_id=client_sdr_id)
    asset_dicts = [asset.to_dict() for asset in assets]

    return jsonify({"message": "Success", "data": asset_dicts}), 200


@CLIENT_BLUEPRINT.route("/all_assets/<int:archetype_id>", methods=["GET"])
@require_user
def get_archetype_assets(client_sdr_id: int, archetype_id: int):
    """Gets all assets for a client sdr"""
    assets = fetch_archetype_assets(client_archetype_id=archetype_id)

    return jsonify({"message": "Success", "data": assets}), 200

@CLIENT_BLUEPRINT.route("/get_spending/<int:client_id>", methods=["GET"])
@require_user
def get_client_spending(client_sdr_id: int, client_id: int):
    """Gets all assets for a client sdr"""
    spending = get_spending(client_sdr_id=client_sdr_id, client_id=client_id)
    return jsonify({"message": "Success", "data": spending}), 200

@CLIENT_BLUEPRINT.route("/clients_list", methods=["GET"])
@require_user
def get_clients_list(client_sdr_id: int):
    clients = get_all_clients(client_sdr_id)
    return jsonify({"message": "Success", "data": clients}), 200


@CLIENT_BLUEPRINT.route("/generate_assets", methods=["POST"])
def post_generate_assets():

    client_id = get_request_parameter(
        "client_id", request, json=True, required=True, parameter_type=int
    )
    text_dump = get_request_parameter(
        "text_dump", request, json=True, required=True, parameter_type=str
    )
    website_url = get_request_parameter(
        "website_url", request, json=True, required=False, parameter_type=str
    )
    additional_prompting = get_request_parameter(
        "additional_prompting", request, json=True, required=False, parameter_type=str
    )

    num_pain_points = get_request_parameter(
        "num_pain_points", request, json=True, required=False, parameter_type=int
    )
    num_value_props = get_request_parameter(
        "num_value_props", request, json=True, required=False, parameter_type=int
    )
    num_social_proof = get_request_parameter(
        "num_social_proof", request, json=True, required=False, parameter_type=int
    )
    num_how_it_works = get_request_parameter(
        "num_how_it_works", request, json=True, required=False, parameter_type=int
    )
    num_pain_points = get_request_parameter(
        "num_pain_points", request, json=True, required=False, parameter_type=int
    )

    num_offers = get_request_parameter(
        "num_offers", request, json=True, required=False, parameter_type=int
    )

    assets = generate_client_assets(
        client_id=client_id,
        text_dump=text_dump,
        website_url=website_url,
        additional_prompting=additional_prompting,
        num_pain_points=num_pain_points,
        num_value_props=num_value_props,
        num_social_proof=num_social_proof,
        num_how_it_works=num_how_it_works,
    )

    if num_offers and num_offers > 0:
        try:
            offers = generate_client_offers(
                client_id=client_id,
                text_dump=text_dump,
                website_url=website_url,
                additional_prompting=additional_prompting,
                num_offers=num_offers,
            )
            assets += offers
        except Exception as e:
            print(e)

    return jsonify({"message": "Success", "data": assets}), 200
