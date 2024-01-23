from flask import Blueprint, request
from src.authentication.decorators import require_user
from src.operator_dashboard.services import (
    create_operator_dashboard_entry,
    get_operator_dashboard_entries_for_sdr,
    mark_task_complete,
    dismiss_task,
)
from src.utils.request_helpers import get_request_parameter

OPERATOR_DASHBOARD_BLUEPRINT = Blueprint("operator_dashboard", __name__)


@OPERATOR_DASHBOARD_BLUEPRINT.route("/")
def index():
    return "OK", 200


@OPERATOR_DASHBOARD_BLUEPRINT.route("/create", methods=["POST"])
@require_user
def post_create_operator_dashboard_entry(client_sdr_id: int):
    urgency = get_request_parameter("urgency", request, json=True, required=True)
    tag = get_request_parameter("tag", request, json=True, required=True)
    emoji = get_request_parameter("emoji", request, json=True, required=True)
    title = get_request_parameter("title", request, json=True, required=True)
    subtitle = get_request_parameter("subtitle", request, json=True, required=True)
    cta = get_request_parameter("cta", request, json=True, required=True)
    cta_url = get_request_parameter("cta_url", request, json=True, required=True)
    status = get_request_parameter("status", request, json=True, required=True)
    due_date = get_request_parameter("due_date", request, json=True, required=True)
    task_type = get_request_parameter("task_type", request, json=True, required=True)
    task_data = get_request_parameter("task_data", request, json=True, required=True)

    entry = create_operator_dashboard_entry(
        client_sdr_id=client_sdr_id,
        urgency=urgency,
        tag=tag,
        emoji=emoji,
        title=title,
        subtitle=subtitle,
        cta=cta,
        cta_url=cta_url,
        status=status,
        due_date=due_date,
        task_type=task_type,
        task_data=task_data,
    )

    return {"entry": entry.to_dict()}, 200


@OPERATOR_DASHBOARD_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_operator_dashboard_entries_for_sdr_endpoint(client_sdr_id: int):
    entries = get_operator_dashboard_entries_for_sdr(sdr_id=client_sdr_id)

    return {"entries": [entry.to_dict() for entry in entries]}, 200


@OPERATOR_DASHBOARD_BLUEPRINT.route("/mark_complete/<int:task_id>", methods=["POST"])
@require_user
def mark_task_complete_endpoint(client_sdr_id: int, task_id: int):
    success = mark_task_complete(client_sdr_id=client_sdr_id, task_id=task_id)
    if not success:
        return {"success": False}, 400

    return {"success": True}, 200


@OPERATOR_DASHBOARD_BLUEPRINT.route("/dismiss/<int:task_id>", methods=["POST"])
@require_user
def dismiss_task_endpoint(client_sdr_id: int, task_id: int):
    success = dismiss_task(client_sdr_id=client_sdr_id, task_id=task_id)
    if not success:
        return {"success": False}, 400

    return {"success": True}, 200
