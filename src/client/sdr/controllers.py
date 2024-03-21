from src.client.services_client_archetype import get_icp_filters_autofill
from app import db
from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.client.sdr.services_client_sdr import (
    compute_sdr_linkedin_health,
    create_sla_schedule,
    get_sla_schedules_for_sdr,
    update_custom_conversion_pct,
    update_sdr_default_transformer_blacklist,
    update_sdr_email_tracking_settings,
    update_sdr_sla_targets,
    update_sla_schedule,
)
from src.utils.datetime.dateparse_utils import convert_string_to_datetime
from src.utils.request_helpers import get_request_parameter

CLIENT_SDR_BLUEPRINT = Blueprint("client/sdr", __name__)


@CLIENT_SDR_BLUEPRINT.route("/messaging/transformer_blocklist", methods=["POST"])
@require_user
def post_transformer_blocklist(client_sdr_id: int):
    """Modifies the default transformer blocklist for a given SDR."""
    blocklist = get_request_parameter(
        "blocklist", request, json=True, required=True, parameter_type=list
    )

    success = update_sdr_default_transformer_blacklist(
        client_sdr_id=client_sdr_id, blocklist=blocklist
    )

    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to update your transformer blocklist. Please try again or contact support.",
                }
            ),
            400,
        )

    return jsonify({"status": "success"}), 200


@CLIENT_SDR_BLUEPRINT.route("/linkedin/health", methods=["GET"])
@require_user
def get_linkedin_health(client_sdr_id: int):
    success, health, details = compute_sdr_linkedin_health(client_sdr_id)
    if not success:
        return (
            jsonify(
                {"status": "error", "message": "Could not compute LinkedIn health"}
            ),
            400,
        )

    return (
        jsonify({"status": "success", "data": {"health": health, "details": details}}),
        200,
    )


@CLIENT_SDR_BLUEPRINT.route("/sla/targets", methods=["PATCH"])
@require_user
def patch_sla_target(client_sdr_id: int):
    weekly_linkedin_target = get_request_parameter(
        "weekly_linkedin_target", request, json=True, required=False, parameter_type=int
    )
    weekly_email_target = get_request_parameter(
        "weekly_email_target", request, json=True, required=False, parameter_type=int
    )

    success, message = update_sdr_sla_targets(
        client_sdr_id=client_sdr_id,
        weekly_linkedin_target=weekly_linkedin_target,
        weekly_email_target=weekly_email_target,
    )

    if not success:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success"}), 200


@CLIENT_SDR_BLUEPRINT.route("/sla/schedule", methods=["GET"])
@require_user
def get_sla_schedule(client_sdr_id: int):
    start_date = get_request_parameter(
        "start_date", request, json=False, required=False, parameter_type=str
    )
    end_date = get_request_parameter(
        "end_date", request, json=False, required=False, parameter_type=str
    )

    start_date = convert_string_to_datetime(start_date) if start_date else None
    end_date = convert_string_to_datetime(end_date) if end_date else None

    schedules = get_sla_schedules_for_sdr(
        client_sdr_id=client_sdr_id, start_date=start_date, end_date=end_date
    )

    return jsonify({"status": "success", "data": {"schedules": schedules}}), 200


@CLIENT_SDR_BLUEPRINT.route("/sla/schedule", methods=["PATCH"])
@require_user
def patch_sla_schedule(client_sdr_id: int):
    sla_schedule_id = get_request_parameter(
        "sla_schedule_id", request, json=True, required=False, parameter_type=int
    )
    start_date = get_request_parameter(
        "start_date", request, json=True, required=False, parameter_type=str
    )
    if not sla_schedule_id and not start_date:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Schedule ID or Start Date must be included",
                }
            ),
            400,
        )

    linkedin_volume = get_request_parameter(
        "linkedin_volume", request, json=True, required=False, parameter_type=int
    )
    linkedin_special_notes = get_request_parameter(
        "linkedin_special_notes", request, json=True, required=False, parameter_type=str
    )
    email_volume = get_request_parameter(
        "email_volume", request, json=True, required=False, parameter_type=int
    )
    email_special_notes = get_request_parameter(
        "email_special_notes", request, json=True, required=False, parameter_type=str
    )

    start_date = convert_string_to_datetime(start_date) if start_date else None

    success, message = update_sla_schedule(
        client_sdr_id=client_sdr_id,
        sla_schedule_id=sla_schedule_id,
        start_date=start_date,
        linkedin_volume=linkedin_volume,
        linkedin_special_notes=linkedin_special_notes,
        email_volume=email_volume,
        email_special_notes=email_special_notes,
    )

    if not success:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success", "data": {}}), 200


@CLIENT_SDR_BLUEPRINT.route("/sla/schedule/bulk", methods=["PATCH"])
@require_user
def patch_sla_schedule_bulk(client_sdr_id: int):
    schedule_volume_map: dict = get_request_parameter(
        "schedule_volume_map", request, json=True, required=True, parameter_type=dict
    )
    new_max_li_target: int = get_request_parameter(
        "new_max_li_target", request, json=True, required=True, parameter_type=int
    )
    new_max_email_target: int = get_request_parameter(
        "new_max_email_sla", request, json=True, required=True, parameter_type=int
    )

    for schedule_data in schedule_volume_map:
        linkedin_volume = schedule_data.get("linkedin_volume")
        linkedin_special_notes = schedule_data.get("linkedin_special_notes")
        email_volume = schedule_data.get("email_volume")
        email_special_notes = schedule_data.get("email_special_notes")
        schedule_id = schedule_data.get("schedule_id")

        success, message = update_sla_schedule(
            client_sdr_id=client_sdr_id,
            sla_schedule_id=schedule_id,
            linkedin_volume=linkedin_volume,
            linkedin_special_notes=linkedin_special_notes,
            email_volume=email_volume,
            email_special_notes=email_special_notes,
        )

        if not success:
            return jsonify({"status": "error", "message": message}), 400

    if new_max_li_target or new_max_email_target:
        success, message = update_sdr_sla_targets(
            client_sdr_id=client_sdr_id,
            weekly_linkedin_target=new_max_li_target,
            weekly_email_target=new_max_email_target,
        )

        if not success:
            return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success", "data": {}}), 200


@CLIENT_SDR_BLUEPRINT.route("/sla/schedule", methods=["POST"])
@require_user
def post_sla_schedule(client_sdr_id: int):
    start_date = get_request_parameter(
        "start_date", request, json=True, required=True, parameter_type=str
    )
    end_date = get_request_parameter(
        "end_date", request, json=True, required=False, parameter_type=str
    )
    linkedin_volume = get_request_parameter(
        "linkedin_volume", request, json=True, required=False, parameter_type=int
    )
    linkedin_special_notes = get_request_parameter(
        "linkedin_special_notes", request, json=True, required=False, parameter_type=str
    )
    email_volume = get_request_parameter(
        "email_volume", request, json=True, required=False, parameter_type=int
    )
    email_special_notes = get_request_parameter(
        "email_special_notes", request, json=True, required=False, parameter_type=str
    )

    start_date = convert_string_to_datetime(start_date) if start_date else None
    end_date = convert_string_to_datetime(end_date) if end_date else None

    schedule_id = create_sla_schedule(
        client_sdr_id=client_sdr_id,
        start_date=start_date,
        end_date=end_date,
        linkedin_volume=linkedin_volume,
        linkedin_special_notes=linkedin_special_notes,
        email_volume=email_volume,
        email_special_notes=email_special_notes,
    )

    return jsonify({"status": "success", "data": {"schedule_id": schedule_id}}), 200


@CLIENT_SDR_BLUEPRINT.route("/conversions", methods=["PATCH"])
@require_user
def patch_custom_conversion_rates(client_sdr_id: int):
    conversion_sent_pct = get_request_parameter(
        "conversion_sent_pct", request, json=True, required=False, parameter_type=float
    )
    conversion_open_pct = get_request_parameter(
        "conversion_open_pct", request, json=True, required=False, parameter_type=float
    )
    conversion_reply_pct = get_request_parameter(
        "conversion_reply_pct", request, json=True, required=False, parameter_type=float
    )
    conversion_demo_pct = get_request_parameter(
        "conversion_demo_pct", request, json=True, required=False, parameter_type=float
    )

    success, message = update_custom_conversion_pct(
        client_sdr_id=client_sdr_id,
        conversion_sent_pct=conversion_sent_pct,
        conversion_open_pct=conversion_open_pct,
        conversion_reply_pct=conversion_reply_pct,
        conversion_demo_pct=conversion_demo_pct,
    )

    if not success:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success"}), 200


@CLIENT_SDR_BLUEPRINT.route("/sdrs_from_emails", methods=["POST"])
# Unprotected route on purpose
def get_sdrs_from_emails_request():
    from src.client.services import get_all_sdrs_from_emails

    emails = get_request_parameter(
        "emails", request, json=True, required=True, parameter_type=list
    )

    results = get_all_sdrs_from_emails(emails=emails)

    return jsonify({"status": "Success", "data": results}), 200


@CLIENT_SDR_BLUEPRINT.route("/icp_filters/autofill", methods=["GET"])
@require_user
def get_icp_filter_autofill(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True, parameter_type=int
    )

    results = get_icp_filters_autofill(client_sdr_id, archetype_id)

    return jsonify({"status": "success", "data": results}), 200


@CLIENT_SDR_BLUEPRINT.route("/email/tracking", methods=["POST"])
@require_user
def post_email_tracking_settings(client_sdr_id: int):
    track_open = get_request_parameter(
        "track_open", request, json=True, required=False, parameter_type=bool
    )
    track_link = get_request_parameter(
        "track_link", request, json=True, required=False, parameter_type=bool
    )

    success = update_sdr_email_tracking_settings(
        client_sdr_id=client_sdr_id, track_open=track_open, track_link=track_link
    )
    if not success:
        return (
            jsonify(
                {"status": "error", "message": "Could not update tracking settings"}
            ),
            400,
        )

    return jsonify({"status": "success"}), 200
