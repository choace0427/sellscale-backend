from flask import Blueprint, jsonify, request

from src.sight_inbox.services import get_inbox_prospects, get_outstanding_inbox
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user


SIGHT_INBOX_BLUEPRINT = Blueprint("sight_inbox", __name__)


@SIGHT_INBOX_BLUEPRINT.route("/<client_sdr_id>")
def index(client_sdr_id: int):
    outstanding_inbox: list = get_outstanding_inbox(client_sdr_id=client_sdr_id)
    return jsonify(outstanding_inbox)


@SIGHT_INBOX_BLUEPRINT.route("/details", methods=["GET"])
@require_user
def get_inbox_details(client_sdr_id: int):

    # get force_admin boolean param
    force_admin = request.args.get("force_admin", default=False, type=bool)

    details = get_inbox_prospects(client_sdr_id, force_admin)

    return (
        jsonify(
            {
                "message": "Success",
                "data": details,
            }
        ),
        200,
    )
