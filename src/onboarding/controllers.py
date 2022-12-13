from flask import Blueprint, request
from src.onboarding.models import SightOnboarding
from src.onboarding.services import (
    create_sight_onboarding,
    update_sight_onboarding,
    get_sight_onboarding,
    is_onboarding_complete,
)
from src.utils.request_helpers import get_request_parameter

ONBOARDING_BLUEPRINT = Blueprint("onboarding", __name__)


@ONBOARDING_BLUEPRINT.route("/", methods=["POST"])
def check_onboarding():
    """ Check if onboarding is complete for a Client SDR

    Returns:
        Status code 200 if onboarding is complete, 404 if not found: 
    """
    client_sdr_id = get_request_parameter("client_sdr_id", request, json=True, required=True)
    onboarding: SightOnboarding = get_sight_onboarding(client_sdr_id)
    if not onboarding:
        return "Client not found", 404

    return is_onboarding_complete(onboarding.client_sdr_id), 200


@ONBOARDING_BLUEPRINT.route("/update", methods=["POST"])
def manual_update_onboarding():
    """ Update onboarding statuses for a Client SDR

    Returns:
        Status code 200 if onboarding is complete, 404 if not found: 
    """
    client_sdr_id = get_request_parameter("client_sdr_id", request, json=True, required=True)
    manual_update_key = get_request_parameter("manual_update_key", request, json=True, required=True)

    onboarding: SightOnboarding = get_sight_onboarding(client_sdr_id)
    if not onboarding:
        return "Client not found", 404
    
    update_sight_onboarding(onboarding.client_sdr_id, manual_update_key)
    return "OK", 200
    