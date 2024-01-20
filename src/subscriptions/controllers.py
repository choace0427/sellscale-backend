from flask import Blueprint, request, jsonify

from src.authentication.decorators import require_user

from src.utils.request_helpers import get_request_parameter


SUBSCRIPTIONS_BLUEPRINT = Blueprint("subscriptions", __name__)


@SUBSCRIPTIONS_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_all_subscriptions(client_sdr_id: int):
    """Gets all subscriptions for a client"""
    from src.subscriptions.services import (
        deactivate_subscription,
        get_subscriptions,
        subscribe_to_slack_notification,
    )

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


@SUBSCRIPTIONS_BLUEPRINT.route("/activate", methods=["POST"])
@require_user
def post_activate_subscription(client_sdr_id: int):
    """Activates a subscription to a Slack notification"""
    slack_notification_id = get_request_parameter(
        "slack_notification_id", request, json=True, required=False, parameter_type=int
    )

    if not slack_notification_id:
        return (
            jsonify(
                {
                    "message": "Missing Slack notification ID",
                }
            ),
            400,
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


@SUBSCRIPTIONS_BLUEPRINT.route("/deactivate", methods=["POST"])
@require_user
def post_deactivate_subscription(client_sdr_id: int):
    """Deactivates a subscription"""
    subscription_id = get_request_parameter(
        "subscription_id", request, json=True, required=True, parameter_type=int
    )

    # Deactivate the subscription
    success = deactivate_subscription(
        client_sdr_id=client_sdr_id,
        subscription_id=subscription_id,
    )
    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to deactivate subscription",
                }
            ),
            400,
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
