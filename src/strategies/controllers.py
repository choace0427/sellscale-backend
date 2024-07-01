from flask import Blueprint, request, jsonify

from src.authentication.decorators import require_user

from src.utils.request_helpers import get_request_parameter


STRATEGIES_BLUEPRINT = Blueprint("strategies", __name__)


@STRATEGIES_BLUEPRINT.route("/echo", methods=["GET"])
@require_user
def get_all_subscriptions(client_sdr_id: int):
    return 'OK', 200