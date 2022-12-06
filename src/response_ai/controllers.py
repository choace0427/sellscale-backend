from flask import Blueprint, request, jsonify
from src.utils.request_helpers import get_request_parameter
from src.response_ai.services import (
    create_response_configuration,
    get_response_configuration,
    update_response_configuration,
)
from src.response_ai.models import ResponseConfiguration

RESPONSE_AI_BLUEPRINT = Blueprint("response_ai", __name__)


@RESPONSE_AI_BLUEPRINT.route("/create", methods=["POST"])
def post_create_response_configuration():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    li_first_follow_up = get_request_parameter(
        "li_first_follow_up", request, json=True, required=False
    )
    li_second_follow_up = get_request_parameter(
        "li_second_follow_up", request, json=True, required=False
    )
    li_third_follow_up = get_request_parameter(
        "li_third_follow_up", request, json=True, required=False
    )

    rc: ResponseConfiguration = ResponseConfiguration.query.get(archetype_id)
    if rc:
        response_configuration = update_response_configuration(
            archetype_id=archetype_id,
            li_first_follow_up=li_first_follow_up,
            li_second_follow_up=li_second_follow_up,
            li_third_follow_up=li_third_follow_up,
        )
    else:
        response_configuration = create_response_configuration(
            archetype_id=archetype_id,
            li_first_follow_up=li_first_follow_up,
            li_second_follow_up=li_second_follow_up,
            li_third_follow_up=li_third_follow_up,
        )
    return jsonify({"response_configuration_id": response_configuration.archetype_id})


@RESPONSE_AI_BLUEPRINT.route("/", methods=["GET"])
def get_response_configuration_endpoint():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    response_configuration = get_response_configuration(archetype_id=archetype_id)
    return jsonify(response_configuration)
