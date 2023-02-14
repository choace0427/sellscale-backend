from flask import Blueprint, request, jsonify
from model_import import ClientSDR
from src.authentication.decorators import require_user


AUTHENTICATION_BLUEPRINT = Blueprint("authentication", __name__)


@AUTHENTICATION_BLUEPRINT.route("/get_client_sdr_name", methods=["GET"])
@require_user
def get_client_sdr_name(client_sdr_id: int):
    """A function to test the require_user decorator.

    Note that we don't return the id, this is for security reasons.
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    return jsonify(sdr.name), 200
