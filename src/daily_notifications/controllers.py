
from flask import Blueprint, request, jsonify
from src.editing_tools.services import get_edited_options
from src.utils.request_helpers import get_request_parameter
from services import update_daily_notification_status

EDITING_TOOLS_BLUEPRINT = Blueprint("daily_notifications", __name__)


@EDITING_TOOLS_BLUEPRINT.route("/update_status", methods=["PUT"])
def put_update_status():
    id = get_request_parameter(
        "id", request, json=True, required=True
    )
    status = get_request_parameter(
        "status", request, json=True, required=True
    )

    if status != "COMPLETE" and status != "CANCELLED":
        return "Invalid status.", 400

    update_daily_notification_status(id=id, status=status)

    return "OK", 200
