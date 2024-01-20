import datetime
from flask import Blueprint, jsonify, request
from app import db

from src.authentication.decorators import require_user
from src.client.archetype.services_client_archetype import (
    bulk_action_move_prospects_to_archetype,
    bulk_action_withdraw_prospect_invitations,
    generate_notification_for_campaign_active,
    get_archetype_generation_upcoming,
    send_slack_notif_campaign_active,
)
from src.client.models import ClientArchetype, ClientSDR
from src.email_outbound.email_store.hunter import (
    find_hunter_emails_for_prospects_under_archetype,
)
from src.li_conversation.models import LinkedinInitialMessageTemplate
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
)
from src.operator_dashboard.services import create_operator_dashboard_entry
from src.prospecting.models import Prospect
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

    templates: list[
        LinkedinInitialMessageTemplate
    ] = LinkedinInitialMessageTemplate.query.filter(
        LinkedinInitialMessageTemplate.client_archetype_id == archetype_id,
    ).all()

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

    research_points = detect_template_research_points(template_str)
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

    archetype.linkedin_active = active
    db.session.commit()

    if active:
        send_slack_notif_campaign_active(client_sdr_id, archetype_id, "LinkedIn")

        generate_notification_for_campaign_active(
            archetype_id=archetype_id,
        )

        create_operator_dashboard_entry(
            client_sdr_id=client_sdr_id,
            urgency=OperatorDashboardEntryPriority.HIGH,
            tag="linkedin_campaign_active_{}".format(archetype_id),
            emoji=archetype.emoji,
            title="Review new LinkedIn Campaign",
            subtitle="Launched campaign for '{}'. Review prospects and copy.".format(
                archetype.archetype
            ),
            cta="Review Campaign",
            cta_url="/setup/linkedin?campaign_id={}".format(archetype_id),
            status=OperatorDashboardEntryStatus.PENDING,
            due_date=datetime.datetime.now() + datetime.timedelta(days=1),
        )

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

    find_hunter_emails_for_prospects_under_archetype.apply_async(
        args=[client_sdr_id, archetype_id]
    )

    archetype.email_active = active
    db.session.commit()

    if active:
        send_slack_notif_campaign_active(client_sdr_id, archetype_id, "email")

        create_operator_dashboard_entry(
            client_sdr_id=client_sdr_id,
            urgency=OperatorDashboardEntryPriority.HIGH,
            tag="email_campaign_active_{}".format(archetype_id),
            emoji=archetype.emoji,
            title="Review new Email Campaign",
            subtitle="Launched campaign for '{}'. Review prospects and copy.".format(
                archetype.archetype
            ),
            cta="Review Campaign",
            cta_url="/setup/email?campaign_id={}".format(archetype_id),
            status=OperatorDashboardEntryStatus.PENDING,
            due_date=datetime.datetime.now() + datetime.timedelta(days=1),
        )

    random_prospects = (
        Prospect.query.filter(
            Prospect.archetype_id == archetype_id,
        )
        .filter(Prospect.icp_fit_score <= 4)
        .order_by(Prospect.icp_fit_score.desc())
        .limit(3)
        .all()
    )
    num_prospects = Prospect.query.filter(
        Prospect.archetype_id == archetype_id,
    ).count()

    first_template = ai_initial_email_prompt(
        client_sdr_id=client_sdr_id,
        prospect_id=random_prospects[0].id,
    )
    email_body = generate_email(prompt=first_template)
    email_body = email_body.get("body")

    if active:
        create_notification(
            client_sdr_id=client_sdr_id,
            title="Review New Campaign",
            subtitle="Launched {}".format(datetime.datetime.now().strftime("%b %d")),
            stars=0,
            cta="View and Mark as Complete",
            data={
                "campaign_name": archetype.archetype,
                "example_message": email_body,
                "render_message_as_html": True,
                "random_prospects": [
                    {
                        "full_name": p.full_name,
                        "linkedin_url": p.linkedin_url,
                        "img_url": p.img_url,
                        "title": p.title,
                        "company": p.company,
                        "icp_fit_score": p.icp_fit_score,
                    }
                    for p in random_prospects
                ],
                "num_prospects": num_prospects,
                "linkedin_active": archetype.linkedin_active,
                "email_active": archetype.email_active,
                "archetype_id": archetype.id,
            },
            priority=OperatorNotificationPriority.HIGH,
            notification_type=OperatorNotificationType.REVIEW_NEW_CAMPAIGN,
        )

    return jsonify({"status": "success"}), 200
