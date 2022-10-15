import re
from flask import Blueprint, jsonify, request
from src.research.linkedin.iscraper import (
    get_linkedin_search_results_from_iscraper,
    get_linkedin_link_from_iscraper,
)

from src.utils.request_helpers import get_request_parameter

from ..message_generation.services import (
    generate_outreaches,
)
from .linkedin.services import (
    get_research_and_bullet_points,
    get_research_and_bullet_points_new,
    reset_prospect_research_and_messages,
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


@RESEARCH_BLUEPRINT.route("/v1/search_linkedin", methods=["POST"])
def search_linkedin_iscraper():
    name = get_request_parameter("name", request, json=True, required=True)
    location = get_request_parameter("location", request, json=True, required=True)

    return jsonify(
        get_linkedin_search_results_from_iscraper(name=name, location=location)
    )


@RESEARCH_BLUEPRINT.route("/v1/search_linkedin/universal_id", methods=["POST"])
def search_linkedin_universal_id():
    name = get_request_parameter("name", request, json=True, required=True)
    location = get_request_parameter("location", request, json=True, required=True)

    return jsonify(get_linkedin_link_from_iscraper(name=name, location=location))


@RESEARCH_BLUEPRINT.route("/v1/wipe_prospect_messages_and_research", methods=["DELETE"])
def wipe_prospect_messages_and_research():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )

    reset_prospect_research_and_messages(prospect_id=prospect_id)

    return "OK", 200


# AAKASH TODO NOTE HERE
# prospects = [
#     659,
#     660,
#     667,
#     672,
#     674,
#     686,
#     687,
#     691,
#     695,
#     713,
#     714,
#     725,
#     726,
#     727,
#     732,
#     736,
#     738,
#     739,
#     744,
#     748,
#     752,
#     767,
#     768,
#     774,
#     776,
#     781,
#     782,
#     783,
#     784,
#     785,
#     786,
#     792,
#     805,
#     813,
#     819,
#     821,
#     823,
# ]
# from src.message_generation.services import (
#     approve_message,
# )
# from app import db
# from model_import import Prospect
# from tqdm import tqdm

# # for prospect_id in prospects:

# for prospect_id in tqdm(prospects):
#     data = db.session.execute(
#         """
#         select length(completion), *
#         from generated_message
#         where prospect_id = {prospect_id}
#         order by abs(280 - length(completion)) asc
#         limit 1;
#     """.format(
#             prospect_id=prospect_id
#         )
#     ).fetchall()[0]
#     approve_message(data["id"])


# return "OK", 200
