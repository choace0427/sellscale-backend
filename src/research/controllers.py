import random
import re
from flask import Blueprint, jsonify, request
from model_import import ClientArchetype
from src.client.models import Client, ClientSDR
from src.prospecting.models import Prospect
from src.research.linkedin.iscraper import (
    get_linkedin_search_results_from_iscraper,
    get_linkedin_link_from_iscraper,
)
from src.research.models import ResearchPoints
from src.research.website.website_metadata_summarizer import (
    process_cache_and_print_website,
)

from src.utils.request_helpers import get_request_parameter
from src.research.services import (
    flag_research_point,
    get_all_research_point_types,
    run_create_custom_research_entries,
    research_point_acceptance_rate,
)

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


@RESEARCH_BLUEPRINT.route("/all_research_point_types", methods=["GET"])
@require_user
def get_all_research_point_types_endpoint(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=False
    )

    return (
        jsonify(
            {"message": "Success", "data": get_all_research_point_types(client_sdr_id=client_sdr_id, archetype_id=int(archetype_id))}
        ),
        200,
    )


@RESEARCH_BLUEPRINT.route("/research_points/heuristic", methods=["GET"])
@require_user
def get_heuristic_research_points(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True
    )
    prospect_id = int(prospect_id)

    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Unauthorized"}), 401

    rps: list[ResearchPoints] = ResearchPoints.get_research_points_by_prospect_id(
        prospect_id
    )
    rps_parsed = [rp.to_dict() for rp in rps]

    return jsonify({"message": "Success", "research_points": rps_parsed}), 200


@RESEARCH_BLUEPRINT.route("/personal_research_points", methods=["GET"])
@require_user
def get_personal_research_points(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True
    )

    points = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    random_sample_points = random.sample(points, min(len(points), 3))
    data = []
    for point in random_sample_points:
        data.append(
            {
                "id": point.id,
                "reason": point.value,
            }
        )

    return jsonify(data)


@RESEARCH_BLUEPRINT.route("/account_research_points", methods=["GET"])
@require_user
def get_account_research_points_endpoint(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.client_sdr_id != client_sdr_id:
        return "Unauthorized", 401

    return jsonify(get_account_research_points_by_prospect_id(prospect_id=prospect_id))


@RESEARCH_BLUEPRINT.route("/research_points/<prospect_id>", methods=["GET"])
@require_user
def get_research_points_by_prospect_id(client_sdr_id: int, prospect_id: int):
    points = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    
    return jsonify({"data": [{"id": point.id, "value": point.value, "research_point_type": point.research_point_type} for point in points]})



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
        "archetype_id", request, json=True, required=False
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=False
    )
    hard_refresh = get_request_parameter(
        "hard_refresh", request, json=True, required=False
    )

    if archetype_id:
        archetype: ClientArchetype = ClientArchetype.query.filter_by(
            id=archetype_id
        ).first()
        if archetype.client_sdr_id != client_sdr_id:
            return "Unauthorized", 401

        success = run_research_extraction_for_prospects_in_archetype(
            archetype_id=archetype_id, hard_refresh=hard_refresh
        )
    elif prospect_id:
        prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        if prospect.client_sdr_id != client_sdr_id:
            return "Unauthorized", 401

        generate_prospect_research(prospect.id, False, hard_refresh)

        success = True
    else:
        success = False

    if success:
        return "OK", 200
    return "Failed to generate research points", 500


@RESEARCH_BLUEPRINT.route("/custom_research_point/upload", methods=["POST"])
@require_user
def post_create_custom_research_points(client_sdr_id: int):

    label = get_request_parameter(
        "label", request, json=True, required=True, parameter_type=str
    )
    category = get_request_parameter(
        "category", request, json=True, required=False, parameter_type=str
    )
    entries = get_request_parameter(
        "entries", request, json=True, required=True, parameter_type=list
    )

    run_create_custom_research_entries.apply_async(
        args=[client_sdr_id, label, entries, category],
        queue="prospecting",
        routing_key="prospecting",
        priority=1,
    )

    return (
        jsonify({"message": "Upload jobs successfully scheduled."}),
        200,
    )


@RESEARCH_BLUEPRINT.route("/acceptance_rates", methods=["GET"])
@require_user
def get_research_point_acceptance_rates(client_sdr_id: int):

    data = research_point_acceptance_rate()

    return jsonify({"message": "Success", "data": data}), 200


@RESEARCH_BLUEPRINT.route("/generate_website_metadata", methods=["POST"])
def get_website_metadata():
    url = get_request_parameter("url", request, json=True, required=True)

    metadata = process_cache_and_print_website(url)
    return jsonify(metadata), 200
