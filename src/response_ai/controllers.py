from flask import Blueprint, request, jsonify
from src.utils.request_helpers import get_request_parameter
from src.response_ai.services import create_response_configuration

RESPONSE_AI_BLUEPRINT = Blueprint("response_ai", __name__)


@RESPONSE_AI_BLUEPRINT.route("/")
def index():
    return "OK", 200


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

    response_configuration = create_response_configuration(
        archetype_id=archetype_id,
        li_first_follow_up=li_first_follow_up,
        li_second_follow_up=li_second_follow_up,
        li_third_follow_up=li_third_follow_up,
    )
    return jsonify({"response_configuration_id": response_configuration.archetype_id})
