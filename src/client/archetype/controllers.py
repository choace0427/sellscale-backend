import datetime
from flask import Blueprint, jsonify, request
from app import db

from src.authentication.decorators import require_user
from src.chatbot.campaign_builder_assistant import selix_campaign_enabled_handler
from src.client.SequenceAutoGeneration import SequenceAutoGenerationParameters, initialize_auto_generation_payload, \
    generate_linkedin_sequence_prompt, generate_email_sequence_prompt
from src.client.archetype.services_client_archetype import (
    bulk_action_move_prospects_to_archetype,
    bulk_action_withdraw_prospect_invitations,
    create_li_init_template_asset_mapping,
    delete_li_init_template_asset_mapping,
    generate_notification_for_campaign_active,
    get_all_li_init_template_assets,
    get_archetype_assets,
    get_archetype_generation_upcoming,
    import_email_sequence,
    import_linkedin_sequence,
    send_slack_notif_campaign_active,
)
from src.automation.orchestrator import add_process_for_future
from src.client.models import Client, ClientArchetype, ClientSDR
from src.client.services import get_client_assets, campaign_voices_generation
from src.email_outbound.email_store.hunter import (
    find_hunter_emails_for_prospects_under_archetype,
)
from src.email_outbound.email_store.services import find_emails_for_archetype
from src.li_conversation.models import (
    LinkedInInitialMessageToAssetMapping,
    LinkedinInitialMessageTemplate,
)
from src.message_generation.email.services import (
    ai_initial_email_prompt,
    generate_email,
)
from src.notifications.models import (
    OperatorNotificationPriority,
    OperatorNotificationType,
)
from src.notifications.services import create_notification
from src.operator_dashboard.models import (
    OperatorDashboardEntryPriority,
    OperatorDashboardEntryStatus,
    OperatorDashboardTaskType,
)
from src.operator_dashboard.services import create_operator_dashboard_entry
from src.prospecting.icp_score.services import update_icp_scoring_ruleset, \
    apply_segment_icp_scoring_ruleset_filters_task, apply_archetype_icp_scoring_ruleset_filters_task
from src.prospecting.models import Prospect
from src.research.models import ResearchPointType
from src.smartlead.services import create_smartlead_campaign
from src.utils.request_helpers import get_request_parameter


CLIENT_ARCHETYPE_BLUEPRINT = Blueprint("client/archetype", __name__)


@CLIENT_ARCHETYPE_BLUEPRINT.route("/generations", methods=["GET"])
@require_user
def get_archetypes_endpoint(client_sdr_id: int):
    active_only = get_request_parameter(
        "active_only", request, json=False, required=False, parameter_type=bool
    )
    client_wide = get_request_parameter(
        "client_wide", request, json=False, required=False, parameter_type=bool
    )

    result = get_archetype_generation_upcoming(
        client_sdr_id=client_sdr_id,
        active_only=active_only,
        client_wide=client_wide,
    )

    return jsonify({"status": "success", "data": result}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/prospects", methods=["GET"])
@require_user
def get_prospects_by_archetype(client_sdr_id: int, archetype_id: int):
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)

    if not archetype:
        return "Archetype not found", 404

    prospects = Prospect.query.filter(
        Prospect.archetype_id == archetype_id
        ).all()

    return jsonify({"prospects": [prospect.simple_to_dict() for prospect in prospects]}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/score", methods=["POST"])
@require_user
def post_score_archetype_with_ruleset(client_sdr_id: int, archetype_id: int):
    client_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.id == archetype_id,
        ).first()

    if not client_archetype:
        return "Cannot find unassigned client archetype", 400

    included_individual_title_keywords = get_request_parameter(
        "included_individual_title_keywords", request, json=True, required=False
    )
    excluded_individual_title_keywords = get_request_parameter(
        "excluded_individual_title_keywords", request, json=True, required=False
    )
    included_individual_industry_keywords = get_request_parameter(
        "included_individual_industry_keywords", request, json=True, required=False
    )
    excluded_individual_industry_keywords = get_request_parameter(
        "excluded_individual_industry_keywords", request, json=True, required=False
    )
    individual_years_of_experience_start = get_request_parameter(
        "individual_years_of_experience_start", request, json=True, required=False
    )
    individual_years_of_experience_end = get_request_parameter(
        "individual_years_of_experience_end", request, json=True, required=False
    )
    included_individual_skills_keywords = get_request_parameter(
        "included_individual_skills_keywords", request, json=True, required=False
    )
    excluded_individual_skills_keywords = get_request_parameter(
        "excluded_individual_skills_keywords", request, json=True, required=False
    )
    included_individual_locations_keywords = get_request_parameter(
        "included_individual_locations_keywords", request, json=True, required=False
    )
    excluded_individual_locations_keywords = get_request_parameter(
        "excluded_individual_locations_keywords", request, json=True, required=False
    )
    included_individual_generalized_keywords = get_request_parameter(
        "included_individual_generalized_keywords", request, json=True, required=False
    )
    excluded_individual_generalized_keywords = get_request_parameter(
        "excluded_individual_generalized_keywords", request, json=True, required=False
    )
    included_individual_education_keywords = get_request_parameter(
        "included_individual_education_keywords", request, json=True, required=False
    )
    excluded_individual_education_keywords = get_request_parameter(
        "excluded_individual_education_keywords", request, json=True, required=False
    )
    included_individual_seniority_keywords = get_request_parameter(
        "included_individual_seniority_keywords", request, json=True, required=False
    )
    excluded_individual_seniority_keywords = get_request_parameter(
        "excluded_individual_seniority_keywords", request, json=True, required=False
    )
    included_company_name_keywords = get_request_parameter(
        "included_company_name_keywords", request, json=True, required=False
    )
    excluded_company_name_keywords = get_request_parameter(
        "excluded_company_name_keywords", request, json=True, required=False
    )
    included_company_locations_keywords = get_request_parameter(
        "included_company_locations_keywords", request, json=True, required=False
    )
    excluded_company_locations_keywords = get_request_parameter(
        "excluded_company_locations_keywords", request, json=True, required=False
    )
    company_size_start = get_request_parameter(
        "company_size_start", request, json=True, required=False
    )
    company_size_end = get_request_parameter(
        "company_size_end", request, json=True, required=False
    )
    included_company_industries_keywords = get_request_parameter(
        "included_company_industries_keywords", request, json=True, required=False
    )
    excluded_company_industries_keywords = get_request_parameter(
        "excluded_company_industries_keywords", request, json=True, required=False
    )
    included_company_generalized_keywords = get_request_parameter(
        "included_company_generalized_keywords", request, json=True, required=False
    )
    excluded_company_generalized_keywords = get_request_parameter(
        "excluded_company_generalized_keywords", request, json=True, required=False
    )
    individual_personalizers = get_request_parameter(
        "individual_personalizers", request, json=True, required=False
    )
    company_personalizers = get_request_parameter(
        "company_personalizers", request, json=True, required=False
    )
    dealbreakers = get_request_parameter(
        "dealbreakers", request, json=True, required=False
    )
    individual_ai_filters = get_request_parameter(
        "individual_ai_filters", request, json=True, required=False
    )
    company_ai_filters = get_request_parameter(
        "company_ai_filters", request, json=True, required=False
    )
    selected_contacts = get_request_parameter(
        "selectedContacts", request, json=True, required=False
    )

    update_icp_scoring_ruleset(
        client_archetype_id=client_archetype.id,
        included_individual_title_keywords=included_individual_title_keywords,
        excluded_individual_title_keywords=excluded_individual_title_keywords,
        included_individual_industry_keywords=included_individual_industry_keywords,
        excluded_individual_industry_keywords=excluded_individual_industry_keywords,
        individual_years_of_experience_start=individual_years_of_experience_start,
        individual_years_of_experience_end=individual_years_of_experience_end,
        included_individual_skills_keywords=included_individual_skills_keywords,
        excluded_individual_skills_keywords=excluded_individual_skills_keywords,
        included_individual_locations_keywords=included_individual_locations_keywords,
        excluded_individual_locations_keywords=excluded_individual_locations_keywords,
        included_individual_generalized_keywords=included_individual_generalized_keywords,
        excluded_individual_generalized_keywords=excluded_individual_generalized_keywords,
        included_company_name_keywords=included_company_name_keywords,
        excluded_company_name_keywords=excluded_company_name_keywords,
        included_company_locations_keywords=included_company_locations_keywords,
        excluded_company_locations_keywords=excluded_company_locations_keywords,
        company_size_start=company_size_start,
        company_size_end=company_size_end,
        included_company_industries_keywords=included_company_industries_keywords,
        excluded_company_industries_keywords=excluded_company_industries_keywords,
        included_company_generalized_keywords=included_company_generalized_keywords,
        excluded_company_generalized_keywords=excluded_company_generalized_keywords,
        included_individual_education_keywords=included_individual_education_keywords,
        excluded_individual_education_keywords=excluded_individual_education_keywords,
        included_individual_seniority_keywords=included_individual_seniority_keywords,
        excluded_individual_seniority_keywords=excluded_individual_seniority_keywords,
        individual_personalizers=individual_personalizers,
        company_personalizers=company_personalizers,
        dealbreakers=dealbreakers,
        individual_ai_filters=individual_ai_filters,
        company_ai_filters=company_ai_filters,
    )

    # If selected contact is empty, we want to score all prospects in the segment
    if not selected_contacts or len(selected_contacts) == 0:
        prospects = Prospect.query.filter(
            Prospect.archetype_id == archetype_id
            ).all()

        prospect_ids = [prospect.id for prospect in prospects]
    else:
        prospect_ids = selected_contacts

    success = apply_archetype_icp_scoring_ruleset_filters_task(
        client_archetype_id=client_archetype.id,
        prospect_ids=prospect_ids,
    )

    if success:
        return {"message": "ok"}, 200

    return "Failed to apply ICP Scoring Ruleset", 500


@CLIENT_ARCHETYPE_BLUEPRINT.route("/bulk_action/move", methods=["POST"])
@require_user
def post_archetype_bulk_action_move_prospects(client_sdr_id: int):
    target_archetype_id = get_request_parameter(
        "target_archetype_id", request, json=True, required=True, parameter_type=int
    )
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )

    # if len(prospect_ids) > 100:
    #     return (
    #         jsonify({"status": "error", "message": "Too many prospects. Limit 100."}),
    #         400,
    #     )

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    target_archetype: ClientArchetype = ClientArchetype.query.get(target_archetype_id)
    if not target_archetype or sdr.id != target_archetype.client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid target archetype"}), 400

    success = bulk_action_move_prospects_to_archetype(
        client_sdr_id=client_sdr_id,
        target_archetype_id=target_archetype_id,
        prospect_ids=prospect_ids,
    )
    if success:
        return (
            jsonify({"status": "success", "data": {"message": "Moved prospects"}}),
            200,
        )

    return jsonify({"status": "error", "message": "Failed to move prospects"}), 400


@CLIENT_ARCHETYPE_BLUEPRINT.route("/bulk_action/withdraw", methods=["POST"])
@require_user
def post_archetype_bulk_action_withdraw_invitations(client_sdr_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )

    success, _ = bulk_action_withdraw_prospect_invitations(
        client_sdr_id=client_sdr_id,
        prospect_ids=prospect_ids,
    )

    if not success:
        return (
            jsonify({"status": "error", "message": "Failed to withdraw invitations"}),
            400,
        )

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "/<int:archetype_id>/message_delay", methods=["PATCH"]
)
@require_user
def patch_archetype_message_delay(client_sdr_id: int, archetype_id: int):
    delay_days = get_request_parameter(
        "delay_days", request, json=True, required=True, parameter_type=int
    )

    if delay_days < 0:
        return (
            jsonify({"status": "error", "message": "Delay days cannot be negative"}),
            400,
        )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    archetype.first_message_delay_days = delay_days
    db.session.commit()

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "/<int:archetype_id>/li_bump_amount", methods=["PATCH"]
)
@require_user
def patch_archetype_li_bump_amount(client_sdr_id: int, archetype_id: int):
    bump_amount = get_request_parameter(
        "bump_amount", request, json=True, required=True, parameter_type=int
    )

    if bump_amount < 1:
        return (
            jsonify(
                {"status": "error", "message": "Delay days must be a whole number"}
            ),
            400,
        )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    archetype.li_bump_amount = bump_amount
    db.session.commit()

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/li_template", methods=["GET"])
@require_user
def get_archetype_li_template(client_sdr_id: int, archetype_id: int):
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    templates: list[LinkedinInitialMessageTemplate] = (
        LinkedinInitialMessageTemplate.query.filter(
            LinkedinInitialMessageTemplate.client_archetype_id == archetype_id,
        ).all()
    )

    return (
        jsonify(
            {
                "status": "success",
                "data": [template.to_dict() for template in templates],
            }
        ),
        200,
    )


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/li_template", methods=["PATCH"])
@require_user
def patch_archetype_li_template(client_sdr_id: int, archetype_id: int):
    template_id = get_request_parameter(
        "template_id", request, json=True, required=True, parameter_type=int
    )
    title = get_request_parameter(
        "title", request, json=True, required=False, parameter_type=str
    )
    message = get_request_parameter(
        "message", request, json=True, required=False, parameter_type=str
    )
    active = get_request_parameter(
        "active", request, json=True, required=False, parameter_type=bool
    )
    times_used = get_request_parameter(
        "times_used", request, json=True, required=False, parameter_type=int
    )
    times_accepted = get_request_parameter(
        "times_accepted", request, json=True, required=False, parameter_type=int
    )
    research_points = get_request_parameter(
        "research_points", request, json=True, required=False, parameter_type=list
    )
    additional_instructions = get_request_parameter(
        "additional_instructions",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    template: LinkedinInitialMessageTemplate = LinkedinInitialMessageTemplate.query.get(
        template_id
    )
    template.title = title or template.title
    template.message = message or template.message
    template.active = active if active is not None else template.active
    template.times_used = times_used or template.times_used
    template.times_accepted = times_accepted or template.times_accepted
    template.research_points = research_points or template.research_points

    if template.additional_instructions is not None:
        template.additional_instructions = additional_instructions
    db.session.commit()

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/li_template", methods=["POST"])
@require_user
def post_archetype_li_template(client_sdr_id: int, archetype_id: int):
    title = get_request_parameter(
        "title", request, json=True, required=True, parameter_type=str
    )
    message = get_request_parameter(
        "message", request, json=True, required=True, parameter_type=str
    )
    sellscale_generated = get_request_parameter(
        "sellscale_generated", request, json=True, required=True, parameter_type=bool
    )
    research_points = get_request_parameter(
        "research_points", request, json=True, required=True, parameter_type=list
    )
    additional_instructions = get_request_parameter(
        "additional_instructions", request, json=True, required=True, parameter_type=str
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not research_points or len(research_points) == 0:
        research_points = ResearchPointType.get_allowedlist_from_blocklist(
            blocklist=sdr.default_transformer_blocklist or []
        )

    template = LinkedinInitialMessageTemplate(
        title=title,
        message=message,
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        active=True,
        times_used=0,
        times_accepted=0,
        sellscale_generated=sellscale_generated,
        research_points=research_points,
        additional_instructions=additional_instructions,
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({"status": "success"}), 201


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/li_template", methods=["DELETE"])
@require_user
def delete_archetype_li_template(client_sdr_id: int, archetype_id: int):
    template_id = get_request_parameter(
        "template_id", request, json=True, required=True, parameter_type=int
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    template: LinkedinInitialMessageTemplate = LinkedinInitialMessageTemplate.query.get(
        template_id
    )
    db.session.delete(template)
    db.session.commit()

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "/<int:archetype_id>/li_template/detect_research", methods=["POST"]
)
@require_user
def post_archetype_li_template_detect_research(client_sdr_id: int, archetype_id: int):
    template_id = get_request_parameter(
        "template_id", request, json=True, required=False, parameter_type=int
    )
    template_str = get_request_parameter(
        "template_str", request, json=True, required=False, parameter_type=str
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    if template_id:
        template: LinkedinInitialMessageTemplate = (
            LinkedinInitialMessageTemplate.query.get(template_id)
        )
        template_str = template.message
    else:
        template = None

    from src.li_conversation.services import detect_template_research_points

    research_points = detect_template_research_points(client_sdr_id, template_str)
    if research_points:
        if template:
            template.research_points = research_points
            db.session.commit()
        return jsonify({"status": "success", "data": research_points}), 200
    else:
        return (
            jsonify({"status": "error", "message": "Failed to detect research points"}),
            500,
        )


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "/<int:archetype_id>/linkedin/active", methods=["POST"]
)
@require_user
def post_archetype_linkedin_active(client_sdr_id: int, archetype_id: int):
    active = get_request_parameter(
        "active", request, json=True, required=True, parameter_type=bool
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    if active and not archetype.linkedin_active:
        meta_data = archetype.meta_data or {}
        has_been_active = meta_data.get("linkedin_has_been_active", False)
        if not has_been_active:
            archetype.meta_data = {
                **meta_data,
                "linkedin_has_been_active": True,
            }
            archetype.linkedin_active = active
            archetype.active = active
            archetype.setup_status = "ACTIVE" if active else "INACTIVE"
            db.session.commit()

            # Send out campaign because it's the first time enabling
            print("Sending out campaign because it's the first time enabling")
            add_process_for_future(
                type="daily_generate_linkedin_campaign_for_sdr",
                args={
                    "client_sdr_id": client_sdr_id,
                },
                minutes=1,
            )

    archetype.linkedin_active = active
    archetype.active = active
    archetype.setup_status = "ACTIVE" if active else "INACTIVE"
    db.session.commit()

    if active:
        generate_notification_for_campaign_active(
            archetype_id=archetype_id,
        )

    selix_campaign_enabled_handler(campaign_id=archetype_id)

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/email/active", methods=["POST"])
@require_user
def post_archetype_email_active(client_sdr_id: int, archetype_id: int):
    active = get_request_parameter(
        "active", request, json=True, required=True, parameter_type=bool
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400
    elif archetype.client_sdr_id != client_sdr_id:
        return (
            jsonify({"status": "error", "message": "Bad archetype, not authorized"}),
            403,
        )

    if active and not archetype.email_active:
        meta_data = archetype.meta_data or {}
        has_been_active = meta_data.get("email_has_been_active", False)
        if not has_been_active:
            archetype.meta_data = {
                **meta_data,
                "email_has_been_active": True,
            }
            archetype.email_active = active
            archetype.active = active
            archetype.setup_status = "ACTIVE" if active else "INACTIVE"
            db.session.commit()

            # Send out campaign because it's the first time enabling
            print("Sending out campaign because it's the first time enabling")
            add_process_for_future(
                type="daily_generate_email_campaign_for_sdr",
                args={
                    "client_sdr_id": client_sdr_id,
                },
                minutes=30,
            )

    archetype.email_active = active
    archetype.active = active
    archetype.setup_status = "ACTIVE" if active else "INACTIVE"
    db.session.commit()

    if active:
        # Find emails for prospects under this archetype
        find_emails_for_archetype(archetype_id=archetype_id)

        # Send slack notification
        send_slack_notif_campaign_active(client_sdr_id, archetype_id, "email")

        # Turn on auto generate and auto sending for this SDR
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        sdr.auto_send_email_campaign = True
        client: Client = Client.query.get(sdr.client_id)
        client.auto_generate_email_messages = True
        db.session.commit()

        # Sync this campaign to Smartlead
        success, message, smartlead_id = create_smartlead_campaign(
            archetype_id=archetype_id,
            sync_to_archetype=True,
        )

        if not success:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Failed to sync to Smartlead: {}".format(message),
                    }
                ),
                400,
            )
        
    selix_campaign_enabled_handler(campaign_id=archetype_id)

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route("/<int:archetype_id>/generate_ai_sequence", methods=["POST"])
@require_user
def post_archetype_generate_ai_sequence(client_sdr_id: int, archetype_id: int):
    auto_generation_payload = get_request_parameter(
        "auto_generation_payload", request, json=True, required=True, parameter_type=dict
    )

    # Get client ID from client SDR ID.
    client_sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    if not client_sdr or not client_sdr.client_id:
        return "Failed to find client ID from auth token", 500

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400

    client: Client = Client.query.get(client_sdr.client_id)

    auto_generation_payload: SequenceAutoGenerationParameters = initialize_auto_generation_payload(auto_generation_payload)

    import pdb; pdb.set_trace()

    if auto_generation_payload.write_email_sequence_draft:
        from src.ml.services import one_shot_sequence_generation
        one_shot_sequence_generation(
            client_sdr_id,
            archetype_id,
            generate_email_sequence_prompt(auto_generation_payload),
            "EMAIL",
            company_name=client.company,
            persona=auto_generation_payload.cta_target,
            with_data=auto_generation_payload.with_data,
        )

    if auto_generation_payload.li_cta_generator:
        print("Generating LI CTA")
        from src.ml.services import one_shot_sequence_generation
        # one_shot_sequence_generation.delay(
        #     client_sdr_id,
        #     archetype_id,
        #     generate_linkedin_sequence_prompt(auto_generation_payload),
        #     "LINKEDIN-CTA"
        # )
        one_shot_sequence_generation.delay(
            client_sdr_id,
            archetype_id,
            generate_linkedin_sequence_prompt(auto_generation_payload),
            "LINKEDIN-CTA",
            num_steps=auto_generation_payload.num_steps,
            num_variants=auto_generation_payload.num_variance,
            company_name=client.company,
            persona=auto_generation_payload.cta_target,
            with_data=auto_generation_payload.with_data,

        )
    elif auto_generation_payload.write_li_sequence_draft:
        print("Generating LI sequence")
        from src.ml.services import one_shot_sequence_generation
        # one_shot_sequence_generation.delay(
        #     client_sdr_id,
        #     archetype_id,
        #     generate_linkedin_sequence_prompt(auto_generation_payload),
        #     "LINKEDIN-TEMPLATE"
        # )
        one_shot_sequence_generation.delay(
            client_sdr_id,
            archetype_id,
            generate_linkedin_sequence_prompt(auto_generation_payload),
            "LINKEDIN-TEMPLATE",
            num_steps=auto_generation_payload.num_steps,
            num_variants=auto_generation_payload.num_variance,
            company_name=client.company,
            persona=auto_generation_payload.cta_target,
            with_data=auto_generation_payload.with_data,
        )

        if auto_generation_payload.selected_voice:
            campaign_voices_generation.delay(
                archetype=archetype,
                with_cta=False,
                with_voice=True,
                with_follow_up=False,
                archetype_id=archetype_id,
                client_id=client_sdr.client_id,
                client_sdr_id=client_sdr_id,
                voice_id=auto_generation_payload.selected_voice,
            )

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "/<int:archetype_id>/import_sequence", methods=["POST"]
)
@require_user
def post_archetype_import_sequence(client_sdr_id: int, archetype_id: int):
    channel_type = get_request_parameter(
        "channel_type", request, json=True, required=True, parameter_type=str
    )
    steps = get_request_parameter(
        "steps", request, json=True, required=True, parameter_type=list
    )
    is_template_mode = get_request_parameter(
        "is_template_mode", request, json=True, required=False, parameter_type=bool
    )
    ctas = get_request_parameter(
        "ctas", request, json=True, required=False, parameter_type=list
    )
    subject_lines = get_request_parameter(
        "subject_lines", request, json=True, required=False, parameter_type=list
    )
    override_sequence = get_request_parameter(
        "override_sequence", request, json=True, required=False, parameter_type=bool
    )

    if channel_type not in ["email", "linkedin"]:
        return jsonify({"status": "error", "message": "Invalid channel type"}), 400

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid archetype"}), 400

    success = False
    if channel_type == "email":
        success = import_email_sequence(
            campaign_id=archetype_id,
            steps=steps,
            subject_lines=subject_lines,
            override_sequence=override_sequence,
        )
    elif channel_type == "linkedin":
        success = import_linkedin_sequence(
            campaign_id=archetype_id,
            steps=steps,
            is_template_mode=is_template_mode,
            ctas=ctas,
            override_sequence=override_sequence,
        )

    if not success:
        return jsonify({"status": "error", "message": "Failed to import sequence"}), 400

    return jsonify({"status": "success"}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route("/assets/<int:archetype_id>", methods=["GET"])
@require_user
def get_assets(client_sdr_id: int, archetype_id: int):
    assets = get_archetype_assets(archetype_id=archetype_id)

    return jsonify({"status": "success", "data": assets}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "li_init_template/create_asset_mapping", methods=["POST"]
)
@require_user
def post_create_li_init_template_asset_mapping(client_sdr_id: int):
    """Creates an asset mapping for a given client SDR"""
    linkedin_initial_message_id = get_request_parameter(
        "linkedin_initial_message_id", request, json=True, required=True
    )
    asset_id = get_request_parameter("asset_id", request, json=True, required=True)

    linkedin_initial_message: LinkedinInitialMessageTemplate = (
        LinkedinInitialMessageTemplate.query.get(linkedin_initial_message_id)
    )
    if not linkedin_initial_message:
        return jsonify({"error": "Linkedin initial message not found."}), 404
    elif linkedin_initial_message.client_sdr_id != client_sdr_id:
        return (
            jsonify({"error": "This Linkedin initial message does not belong to you."}),
            401,
        )

    create_li_init_template_asset_mapping(
        linkedin_initial_message_id=linkedin_initial_message_id,
        client_assets_id=asset_id,
    )

    return jsonify({"message": "Asset mapping created."}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "li_init_template/delete_asset_mapping", methods=["POST"]
)
@require_user
def post_delete_li_init_template_asset_mapping(client_sdr_id: int):
    """Deletes an asset mapping for a given client SDR"""
    linkedin_initial_message_to_asset_mapping_id = get_request_parameter(
        "linkedin_initial_message_to_asset_mapping_id",
        request,
        json=True,
        required=True,
    )

    linkedin_initial_message_to_asset_mapping: LinkedInInitialMessageToAssetMapping = (
        LinkedInInitialMessageToAssetMapping.query.get(
            linkedin_initial_message_to_asset_mapping_id
        )
    )
    linkedin_initial_message_id: int = (
        linkedin_initial_message_to_asset_mapping.linkedin_initial_message_id
    )
    linkedin_initial_message: LinkedinInitialMessageTemplate = (
        LinkedinInitialMessageTemplate.query.get(linkedin_initial_message_id)
    )
    if not linkedin_initial_message:
        return jsonify({"error": "Linkedin initial message not found."}), 404
    elif linkedin_initial_message.client_sdr_id != client_sdr_id:
        return (
            jsonify({"error": "This Linkedin initial message does not belong to you."}),
            401,
        )

    delete_li_init_template_asset_mapping(
        linkedin_initial_message_to_asset_mapping_id=linkedin_initial_message_to_asset_mapping_id
    )

    return jsonify({"message": "Asset mapping deleted."}), 200


@CLIENT_ARCHETYPE_BLUEPRINT.route(
    "li_init_template/get_all_asset_mapping", methods=["GET"]
)
@require_user
def get_li_init_template_all_asset_mapping(client_sdr_id: int):
    """Gets all asset mapping for a given client SDR"""
    linkedin_initial_message_id = get_request_parameter(
        "linkedin_initial_message_id", request, json=False, required=True
    )

    linkedin_initial_message: LinkedinInitialMessageTemplate = (
        LinkedinInitialMessageTemplate.query.get(linkedin_initial_message_id)
    )
    if not linkedin_initial_message:
        return jsonify({"error": "Linkedin initial message not found."}), 404
    elif linkedin_initial_message.client_sdr_id != client_sdr_id:
        return (
            jsonify({"error": "This Linkedin initial message does not belong to you."}),
            401,
        )

    mappings = get_all_li_init_template_assets(
        linkedin_initial_message_id=linkedin_initial_message_id
    )

    return jsonify({"mappings": mappings}), 200
