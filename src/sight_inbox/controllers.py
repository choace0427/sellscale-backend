from flask import Blueprint, jsonify, request

from src.sight_inbox.services import get_outstanding_inbox
from src.utils.request_helpers import get_request_parameter


SIGHT_INBOX_BLUEPRINT = Blueprint("sight_inbox", __name__)


@SIGHT_INBOX_BLUEPRINT.route("/<client_sdr_id>")
def index(client_sdr_id: int):
    outstanding_inbox: list = get_outstanding_inbox(client_sdr_id=client_sdr_id)
    return jsonify(outstanding_inbox)
