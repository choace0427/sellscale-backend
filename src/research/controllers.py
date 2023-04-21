import re
from flask import Blueprint, jsonify, request
from model_import import ClientArchetype
from src.prospecting.models import Prospect
from src.research.linkedin.iscraper import (
    get_linkedin_search_results_from_iscraper,
    get_linkedin_link_from_iscraper,
)

from src.utils.request_helpers import get_request_parameter
from src.research.services import flag_research_point, get_all_research_point_types

from .linkedin.services import (
    get_research_and_bullet_points_new,
    reset_prospect_research_and_messages,
    reset_batch_of_prospect_research_and_messages,
)
from src.research.account_research import (
    run_research_extraction_for_prospects_in_archetype,
    generate_prospect_research,
    get_account_research_points_by_prospect_id,
    get_account_research_points_inputs,
)
from src.authentication.decorators import require_user

RESEARCH_BLUEPRINT = Blueprint("research", __name__)


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


@RESEARCH_BLUEPRINT.route(
    "/v1/batch_wipe_prospect_messages_and_research", methods=["DELETE"]
)
def batch_wipe_prospect_messages_and_research():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    reset_batch_of_prospect_research_and_messages(prospect_ids=prospect_ids)
    return "OK", 200


@RESEARCH_BLUEPRINT.route("/v1/flag_research_point", methods=["POST"])
def flag_research():
    research_point_id = get_request_parameter(
        "research_point_id", request, json=True, required=True
    )
    success = flag_research_point(research_point_id=research_point_id)
    if success:
        return "OK", 200
    return "Failed to flag point", 500


@RESEARCH_BLUEPRINT.route("/all_research_point_types_details", methods=["GET"])
def get_all_research_point_types_details():
    return jsonify(get_all_research_point_types())


@RESEARCH_BLUEPRINT.route("/account_research_points", methods=["GET"])
@require_user
def get_account_research_points(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True
    )

    prospect = Prospect.query.filter_by(id=prospect_id).first()
    if prospect.client_sdr_id != client_sdr_id:
        return "Unauthorized", 401

    return jsonify(get_account_research_points_by_prospect_id(prospect_id=prospect_id))


@RESEARCH_BLUEPRINT.route("/account_research_points/inputs", methods=["GET"])
@require_user
def get_account_research_points_inputs_endpoint(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True
    )

    archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=archetype_id
    ).first()
    if archetype.client_sdr_id != client_sdr_id:
        return "Unauthorized", 401

    return jsonify(get_account_research_points_inputs(archetype_id=archetype_id))


@RESEARCH_BLUEPRINT.route("/account_research_points/generate", methods=["POST"])
@require_user
def generate_account_research_points_endpoint(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    hard_refresh = get_request_parameter(
        "hard_refresh", request, json=True, required=False
    )

    archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=archetype_id
    ).first()
    if archetype.client_sdr_id != client_sdr_id:
        return "Unauthorized", 401

    success = run_research_extraction_for_prospects_in_archetype(
        archetype_id=archetype_id, hard_refresh=hard_refresh
    )

    if success:
        return "OK", 200
    return "Failed to generate research points", 500
