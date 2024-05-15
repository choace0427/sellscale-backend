from flask import Blueprint, request, jsonify
from src.individual.services import (
    backfill_iscraper_cache,
    backfill_prospects,
    convert_to_prospects,
    get_individual,
    start_upload_from_urn_ids,
    get_all_individuals,
    get_uploads,
    start_crawler_on_linkedin_public_id,
    start_upload,
)
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message, URL_MAP
from app import db
import os

INDIVIDUAL_BLUEPRINT = Blueprint("individual", __name__)


@INDIVIDUAL_BLUEPRINT.route("/uploads", methods=["GET"])
# No authentication required for now
def get_individuals_uploads():

    uploads = get_uploads()

    return (
        jsonify(
            {
                "status": "success",
                "data": uploads,
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/upload", methods=["POST"])
# No authentication required for now
def post_individuals_upload():

    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    data = (
        get_request_parameter(
            "data", request, json=True, required=True, parameter_type=list
        )
        or []
    )

    client_id = get_request_parameter(
        "client_id", request, json=True, required=False, parameter_type=int
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=False, parameter_type=int
    )

    uploads = start_upload(name, data, client_id, client_archetype_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": uploads,
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/upload_from_urn_ids", methods=["POST"])
# No authentication required for now
def post_add_from_urn_ids():

    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    urn_ids = (
        get_request_parameter(
            "urn_ids", request, json=True, required=True, parameter_type=list
        )
        or []
    )

    uploads = start_upload_from_urn_ids(name, urn_ids)

    return (
        jsonify(
            {
                "status": "success",
                "data": uploads,
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/start_crawler", methods=["POST"])
# No authentication required for now
def post_start_crawler():

    public_li_id = get_request_parameter(
        "public_li_id", request, json=True, required=True, parameter_type=str
    )

    start_crawler_on_linkedin_public_id(public_li_id)

    return (
        jsonify(
            {
                "status": "success",
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/backfill-prospects", methods=["POST"])
@require_user
def post_backfill_prospects(client_sdr_id: int):

    results = backfill_prospects(client_sdr_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": results,
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/convert-to-prospects", methods=["POST"])
@require_user
def post_convert_to_prospects(client_sdr_id: int):

    client_archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=False, parameter_type=int
    )
    segment_id = get_request_parameter(
        "segment_id", request, json=True, required=False, parameter_type=int
    )

    individual_ids = (
        get_request_parameter(
            "individual_ids", request, json=True, required=True, parameter_type=list
        )
        or []
    )

    prospect_ids = convert_to_prospects(
        client_sdr_id=client_sdr_id,
        individual_ids=individual_ids,
        client_archetype_id=client_archetype_id,
        segment_id=segment_id,
    )

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "prospect_ids": prospect_ids,
                },
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/backfill-iscraper-cache", methods=["POST"])
@require_user
def post_backfill_iscraper_cache(client_sdr_id: int):

    start_index = get_request_parameter(
        "start_index", request, json=True, required=True, parameter_type=int
    )
    end_index = get_request_parameter(
        "end_index", request, json=True, required=True, parameter_type=int
    )

    results = backfill_iscraper_cache(start_index, end_index)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "total": len(results),
                    # "results": results,
                },
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_all_individuals_request(client_sdr_id: int):

    client_archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True, parameter_type=int
    )
    limit = (
        get_request_parameter(
            "limit", request, json=False, required=False, parameter_type=int
        )
        or 100
    )
    offset = (
        get_request_parameter(
            "offset", request, json=False, required=False, parameter_type=int
        )
        or 0
    )

    results, count = get_all_individuals(client_archetype_id, limit, offset)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "total": count,
                    "results": results,
                },
            }
        ),
        200,
    )


@INDIVIDUAL_BLUEPRINT.route("/single", methods=["GET"])
def get_individual_request():
    """
    Endpoint to retrieve an individual's details either by LinkedIn public ID or email.

    Parameters:
    - li_public_id (str): LinkedIn public ID of the individual (optional).
    - email (str): Email address of the individual (optional).

    Returns:
    - JSON response containing the status and the individual's data if found.
    - HTTP status code 200 on success, or appropriate error code on failure.
    """
    li_public_id = get_request_parameter(
        "li_public_id", request, json=False, required=False, parameter_type=str
    )
    email = get_request_parameter(
        "email", request, json=False, required=False, parameter_type=str
    )

    result = get_individual(li_public_id=li_public_id, email=email)

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
            }
        ),
        200,
    )
