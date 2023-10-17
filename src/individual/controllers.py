from flask import Blueprint, request, jsonify
from src.individual.services import backfill_iscraper_cache, backfill_prospects, get_all_individuals, get_uploads, start_crawler_on_linkedin_public_id, start_upload
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
    data = get_request_parameter(
        "data", request, json=True, required=True, parameter_type=list
    ) or []

    uploads = start_upload(name, data)

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
    limit = get_request_parameter(
        "limit", request, json=False, required=False, parameter_type=int
    ) or 100
    offset = get_request_parameter(
        "offset", request, json=False, required=False, parameter_type=int
    ) or 0

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

