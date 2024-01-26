from flask import Blueprint, jsonify

from src.authentication.decorators import require_user
from src.merge_crm.services import create_link_token


MERGE_CRM = Blueprint("merge_crm", __name__)


@MERGE_CRM.route("/link", methods=["POST"])
@require_user
def link(client_sdr_id: int):
    token = create_link_token(client_sdr_id=client_sdr_id)

    return jsonify({"link_token": token})
