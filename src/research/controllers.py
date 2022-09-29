from flask import Blueprint, jsonify, request

from src.utils.request_helpers import get_request_parameter

from ..message_generation.services import (
    generate_outreaches,
)
from .linkedin.services import (
    get_research_and_bullet_points,
    get_research_and_bullet_points_new,
)

RESEARCH_BLUEPRINT = Blueprint("research", __name__)


@RESEARCH_BLUEPRINT.route("/<linkedin_id>")
def research_linkedin(linkedin_id: str):
    data = get_research_and_bullet_points(profile_id=linkedin_id, test_mode=False)
    outreaches = generate_outreaches(research_and_bullets=data, num_options=4)

    return jsonify({"source": data, "outreaches": outreaches})


@RESEARCH_BLUEPRINT.route("/v1/linkedin", methods=["POST"])
def research_linkedin_v1():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    test_mode = get_request_parameter("test_mode", request, json=True, required=True)

    payload = get_research_and_bullet_points_new(
        prospect_id=prospect_id, test_mode=test_mode
    )

    return jsonify(payload)
