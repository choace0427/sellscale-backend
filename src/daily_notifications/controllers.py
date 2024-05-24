from flask import Blueprint, request, jsonify
from src.daily_notifications.models import DailyNotification
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.daily_notifications.services import (
    update_daily_notification_status,
    fill_in_daily_notifications,
    get_engagement_feed_items_for_sdr,
)
from src.utils.datetime.dateutils import get_datetime_now
from datetime import timedelta

DAILY_NOTIFICATIONS_BLUEPRINT = Blueprint("daily_notifications", __name__)


@DAILY_NOTIFICATIONS_BLUEPRINT.route("/<client_sdr_id>")
def get_daily_notifications(client_sdr_id):
    notifications = DailyNotification.query.filter(
        DailyNotification.client_sdr_id == client_sdr_id,
        DailyNotification.status == "PENDING",
        DailyNotification.updated_at >= get_datetime_now() - timedelta(hours=24),
    ).all()

    return jsonify([notification.to_dict() for notification in notifications]), 200


@DAILY_NOTIFICATIONS_BLUEPRINT.route("/fetch", methods=["POST"])
def post_fetch_daily_notifications():
    """Populated the daily notifications table.
    Warning: This is a very expensive operation that will hold up the server for a while.
    TODO: Disable this endpoint in production.
    """
    return fill_in_daily_notifications()


@DAILY_NOTIFICATIONS_BLUEPRINT.route("/update_status", methods=["PUT"])
def put_update_status():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    type = get_request_parameter("type", request, json=True, required=True)
    status = get_request_parameter("status", request, json=True, required=True)

    if status != "COMPLETE" and status != "CANCELLED":
        return "Invalid status.", 400

    return update_daily_notification_status(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id, type=type, status=status
    )


@DAILY_NOTIFICATIONS_BLUEPRINT.route("/engagement/feed", methods=["GET"])
@require_user
def get_engagement_feed(client_sdr_id: int):
    """Gets the engagement feed for the client SDR with id client_sdr_id."""
    limit = int(get_request_parameter("limit", request, required=False)) or 10
    offset = int(get_request_parameter("offset", request, required=False)) or 0

    total_count, items = get_engagement_feed_items_for_sdr(client_sdr_id, limit, offset)

    return (
        jsonify(
            {
                "message": "Success",
                "engagement_feed_items": items,
                "total_count": total_count,
            }
        ),
        200,
    )
