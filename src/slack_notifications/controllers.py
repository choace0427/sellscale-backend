from flask import Blueprint, request, jsonify

from src.authentication.decorators import require_user
from src.slack_notifications.slack_notification import SlackNotificationClass
from src.utils.request_helpers import get_request_parameter
from src.slack_notifications.models import (
    SlackNotification,
    SlackNotificationType,
    get_slack_notification_type_metadata,
)


SLACK_NOTIFICATION_BLUEPRINT = Blueprint("slack_notification", __name__)


@SLACK_NOTIFICATION_BLUEPRINT.route("/test", methods=["POST"])
@require_user
def post_test_slack_notification(client_sdr_id: int):
    """Tests a Slack notification"""

    # Get the Slack notification ID
    slack_notification_id = get_request_parameter(
        "slack_notification_id", request, json=True, required=False, parameter_type=int
    )
    slack_notification: SlackNotification = SlackNotification.query.get(
        slack_notification_id
    )
    if not slack_notification:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Slack notification does not exist",
                }
            ),
            400,
        )

    slack_notification_type: SlackNotificationType = (
        slack_notification.notification_type
    )
    notification: SlackNotificationClass = get_slack_notification_type_metadata()[
        slack_notification_type
    ](client_sdr_id=client_sdr_id, developer_mode=False)
    success = notification.send_test_notification()

    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Error sending Slack notification",
                }
            ),
            500,
        )

    return (
        jsonify(
            {
                "status": "success",
                "message": "Success",
            }
        ),
        200,
    )
