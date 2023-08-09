from flask import Blueprint, request, jsonify
from src.company.services import (
    company_backfill,
    company_backfill_prospects,
)
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message, URL_MAP
from app import db
import os

INDIVIDUAL_BLUEPRINT = Blueprint("individual", __name__)


@INDIVIDUAL_BLUEPRINT.route("/backfill-prospects", methods=["POST"])
@require_user
def post_backfill_prospects(client_sdr_id: int):

    processed_count = company_backfill_prospects(client_sdr_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "processed_count": processed_count,
                },
            }
        ),
        200,
    )
