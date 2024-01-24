from flask import Blueprint, request, jsonify

from src.authentication.decorators import require_user
from src.slack.slack_notification_class import SlackNotificationClass
from src.utils.request_helpers import get_request_parameter
from src.slack.models import (
    SlackNotification,
    SlackNotificationType,
    get_slack_notification_type_metadata,
)


SLACK_BLUEPRINT = Blueprint("slack", __name__)


@SLACK_BLUEPRINT.route("/notification/preview", methods=["POST"])
@require_user
def post_preview_slack_notification(client_sdr_id: int):
    """Previews a Slack notification"""

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
    notification: SlackNotificationClass = slack_notification_type.get_class()(
        client_sdr_id=client_sdr_id, developer_mode=False
    )
    success = notification.send_notification_preview()

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
