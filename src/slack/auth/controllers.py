import os

from flask import Blueprint, request, jsonify

from src.authentication.decorators import require_user
from src.slack.auth.services import exchange_slack_auth_code
from src.utils.request_helpers import get_request_parameter


SLACK_AUTH_BLUEPRINT = Blueprint("slack/authentication", __name__)


@SLACK_AUTH_BLUEPRINT.route("/exchange", methods=["POST"])
@require_user
def post_slack_exchange(client_sdr_id: int):
    """Exchanges the Slack OAuth code for an access token

    Returns:
        dict: The Slack OAuth response
    """
    code = get_request_parameter(
        "code", request, json=True, required=True, parameter_type=str
    )

    success, error = exchange_slack_auth_code(client_sdr_id=client_sdr_id, code=code)

    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": error,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "status": "success",
            }
        ),
        200,
    )
