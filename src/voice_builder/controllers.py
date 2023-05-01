from flask import Blueprint, jsonify, request

from model_import import ClientSDR
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user

from src.voice_builder.services import conduct_research_for_n_prospects

VOICE_BUILDER_BLUEPRINT = Blueprint("voice_builder", __name__)


@VOICE_BUILDER_BLUEPRINT.route("/generate_research", methods=["GET"])
@require_user
def get_account_research_points(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id: int = client_sdr.client_id

    n = get_request_parameter("n", request, json=True, required=True)

    success = conduct_research_for_n_prospects(client_id=client_id, n=n)
    if success:
        return "Success", 200
    return "Failure", 500
