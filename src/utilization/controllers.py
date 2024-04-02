from flask import Blueprint, request, jsonify
from src.client.models import ClientSDR
from src.authentication.decorators import require_user
from src.utilization.services import (get_active_campaign_data, get_rep_needed_campaign_data, get_ai_is_setting_up_campaign_data, get_no_campaign_data, get_completed_campaign_data, get_seat_utilization_data)

UTILIZATION_BLUEPRINT = Blueprint("utilization", __name__)

@UTILIZATION_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_utilization_data(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    activeData = get_active_campaign_data(client_id)
    repData = get_rep_needed_campaign_data(client_id)
    aiData = get_ai_is_setting_up_campaign_data(client_id)
    noData = get_no_campaign_data(client_id)
    completedData = get_completed_campaign_data(client_id)
    seatUtilizationData = get_seat_utilization_data(client_id)

    data = jsonify({
        "active_campaign": activeData,
        "rep_needed_campaign": repData,
        "ai_setting_up": aiData,
        "no_campaign": noData,
        "completed_campaign": completedData,
        "seat_utilization": seatUtilizationData,
    })

    return data
