
from flask import Blueprint, request, jsonify
from src.daily_notifications.models import DailyNotification
from src.editing_tools.services import get_edited_options
from src.utils.request_helpers import get_request_parameter
from src.daily_notifications.services import update_daily_notification_status

DAILY_NOTIFICATIONS_BLUEPRINT = Blueprint("daily_notifications", __name__)

@DAILY_NOTIFICATIONS_BLUEPRINT.route("/<client_sdr_id>")
def get_daily_notifications(client_sdr_id):
    
    notifications = DailyNotification.query.filter(
        DailyNotification.client_sdr_id == client_sdr_id,
    ).order_by(DailyNotification.due_date.desc()).all()

    return jsonify([dict(notification) for notification in notifications]), 200


@DAILY_NOTIFICATIONS_BLUEPRINT.route("/update_status", methods=["PUT"])
def put_update_status():
    id = get_request_parameter(
        "id", request, json=True, required=True
    )
    status = get_request_parameter(
        "status", request, json=True, required=True
    )

    if status != "COMPLETE" and status != "CANCELLED":
        return "Invalid status.", 400

    return update_daily_notification_status(id=id, status=status)
