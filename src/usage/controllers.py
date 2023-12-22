from flask import Blueprint, request, jsonify
from src.client.models import ClientSDR
from src.utils.request_helpers import get_request_parameter
from src.usage.services import (
    get_response_prospecting_service,
    get_created_prospect,
    get_touchsent_prospect,
    get_enriched_prospect,
    get_followupsent_prospect,
    get_replies_prospect,
    get_nurture_prospect,
    get_removed_prospect,
)
from src.authentication.decorators import require_user

USAGE_BLUEPRINT = Blueprint("usage", __name__)


@USAGE_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_response_prospecting_endpoint(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    result = get_response_prospecting_service(client_id=client_id)

    column_names = result.keys()
    response_dict = {col: result[col] for col in column_names}

    create_result = get_created_prospect(client_id=client_id)
    touchsent_result = get_touchsent_prospect(client_id=client_id)
    enriched_result = get_enriched_prospect(client_id=client_id)
    followUpSent_result = get_followupsent_prospect(client_id=client_id)
    replies_result = get_replies_prospect(client_id=client_id)
    nurture_result = get_nurture_prospect(client_id=client_id)
    removed_result = get_removed_prospect(client_id=client_id)

    print(
        create_result,
        touchsent_result,
        enriched_result,
        followUpSent_result,
        replies_result,
        nurture_result,
        removed_result,
    )

    return {
        "prospecting": response_dict,
        "create_prospect": create_result,
        "touch_sent_prospect": touchsent_result,
        "enriched_prospect": enriched_result,
        "follow_up_sent_prospect": followUpSent_result,
        "replies_prospect": replies_result,
        "nurture_prospect": nurture_result,
        "removed_prospect": removed_result,
    }
