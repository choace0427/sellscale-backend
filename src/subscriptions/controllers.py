from flask import Blueprint, request, jsonify

from src.authentication.decorators import require_user
from src.subscriptions.services import (
    deactivate_subscription,
    get_subscriptions,
    subscribe_to_slack_notification,
)
from src.utils.request_helpers import get_request_parameter


SUBSCRIPTIONS_BLUEPRINT = Blueprint("subscriptions", __name__)


@SUBSCRIPTIONS_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_all_subscriptions(client_sdr_id: int):
    """Gets all subscriptions for a client"""
    subscriptions = get_subscriptions(client_sdr_id=client_sdr_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": subscriptions,
            }
        ),
        200,
    )


@SUBSCRIPTIONS_BLUEPRINT.route("/slack/activate", methods=["POST"])
@require_user
def post_slack_subscription(client_sdr_id: int):
    """Activates a subscription to a Slack notification"""
    slack_notification_id = get_request_parameter(
        "slack_notification_id", request, json=True, required=True, parameter_type=int
    )

    # Activate or create the subscription
    id = subscribe_to_slack_notification(
        client_sdr_id=client_sdr_id,
        slack_notification_id=slack_notification_id,
    )

    if not id:
        return (
            jsonify(
                {
                    "message": "Failed to subscribe to Slack notification",
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "message": "Success",
                "data": {"subscription_id": id},
            }
        ),
        200,
    )


@SUBSCRIPTIONS_BLUEPRINT.route("/slack/deactivate", methods=["PATCH"])
@require_user
def patch_slack_subscription(client_sdr_id: int):
    """Deactivates a subscription to a Slack notification"""
    subscription_id = get_request_parameter(
        "subscription_id", request, json=True, required=True, parameter_type=int
    )

    # Deactivate the subscription
    success, reason = deactivate_subscription(
        client_sdr_id=client_sdr_id,
        subscription_id=subscription_id,
    )
    if not success:
        return (
            jsonify(
                {
                    "message": reason,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "message": "Success",
            }
        ),
        200,
    )
