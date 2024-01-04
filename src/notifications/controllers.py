from flask import Blueprint
from src.authentication.decorators import require_user
from src.notifications.models import OperatorNotification
from src.notifications.services import get_notifications_for_sdr, mark_task_complete

NOTIFICATION_BLUEPRINT = Blueprint("notification", __name__)


@NOTIFICATION_BLUEPRINT.route("/")
def index():
    return "OK", 200


@NOTIFICATION_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_notifications_for_sdr_endpoint(client_sdr_id: int):
    notifications = get_notifications_for_sdr(sdr_id=client_sdr_id)

    return {"notifications": notifications}, 200


@NOTIFICATION_BLUEPRINT.route("/mark_complete/<int:task_id>", methods=["POST"])
@require_user
def mark_task_complete_endpoint(client_sdr_id: int, task_id: int):
    notification: OperatorNotification = OperatorNotification.query.filter_by(
        id=task_id
    ).first()

    if notification.client_sdr_id != client_sdr_id:
        return {"success": False}, 400

    success = mark_task_complete(task_id=task_id)
    if not success:
        return {"success": False}, 400

    return {"success": True}, 200
