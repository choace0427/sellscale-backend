from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.prospecting.models import Prospect
from src.segment.models import Segment
from src.segment.services import (
    add_prospects_to_segment,
    create_new_segment,
    delete_segment,
    extract_data_from_sales_navigator_link,
    find_prospects_by_segment_filters,
    get_segments_for_sdr,
    update_segment,
    wipe_segment_ids_from_prospects_in_segment,
)
from src.utils.request_helpers import get_request_parameter

SEGMENT_BLUEPRINT = Blueprint("segment", __name__)


@SEGMENT_BLUEPRINT.route("/")
def index():
    return "OK", 200


@SEGMENT_BLUEPRINT.route("/create", methods=["POST"])
@require_user
def create_segment(client_sdr_id: int):
    segment_title = get_request_parameter(
        "segment_title", request, json=True, required=True
    )
    filters = get_request_parameter("filters", request, json=True, required=True)

    segment: Segment = create_new_segment(
        client_sdr_id=client_sdr_id, segment_title=segment_title, filters=filters
    )

    if segment:
        return segment.to_dict(), 200
    else:
        return "Segment creation failed", 400


@SEGMENT_BLUEPRINT.route("/<int:segment_id>", methods=["GET"])
@require_user
def get_segment(client_sdr_id: int, segment_id: int):
    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if segment:
        return segment.to_dict(), 200
    else:
        return "Segment not found", 404


@SEGMENT_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_segments(client_sdr_id: int):
    segments: list[dict] = get_segments_for_sdr(client_sdr_id)

    return {"segments": segments}, 200


@SEGMENT_BLUEPRINT.route("/<int:segment_id>", methods=["PATCH"])
@require_user
def update_segment_endpoint(client_sdr_id: int, segment_id: int):
    segment_title = get_request_parameter("segment_title", request, json=True)
    filters = get_request_parameter("filters", request, json=True)

    segment: Segment = update_segment(
        client_sdr_id=client_sdr_id,
        segment_id=segment_id,
        segment_title=segment_title,
        filters=filters,
    )

    if segment:
        return segment.to_dict(), 200
    else:
        return "Segment update failed", 400


@SEGMENT_BLUEPRINT.route("/<int:segment_id>", methods=["DELETE"])
@require_user
def delete_segment_endpoint(client_sdr_id: int, segment_id: int):
    success, message = delete_segment(
        client_sdr_id=client_sdr_id, segment_id=segment_id
    )

    if success:
        return "Segment deleted", 200

    return message, 400


@SEGMENT_BLUEPRINT.route("/<int:segment_id>/prospects", methods=["POST"])
@require_user
def add_prospects_to_segment_endpoint(client_sdr_id: int, segment_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    prospects_for_sdr_in_ids = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id, Prospect.id.in_(prospect_ids)
    ).all()
    filtered_ids = [prospect.id for prospect in prospects_for_sdr_in_ids]

    success, message = add_prospects_to_segment(
        prospect_ids=filtered_ids, new_segment_id=segment_id
    )

    if success:
        return "Prospects added to segment", 200

    return message, 400


@SEGMENT_BLUEPRINT.route("/find_prospects", methods=["POST"])
@require_user
def find_prospects_by_segment_filters_endpoint(client_sdr_id: int):
    segment_ids = get_request_parameter("segment_ids", request, json=True)
    included_title_keywords = get_request_parameter(
        "included_title_keywords", request, json=True
    )
    excluded_title_keywords = get_request_parameter(
        "excluded_title_keywords", request, json=True
    )
    included_seniority_keywords = get_request_parameter(
        "included_seniority_keywords", request, json=True
    )
    excluded_seniority_keywords = get_request_parameter(
        "excluded_seniority_keywords", request, json=True
    )
    included_company_keywords = get_request_parameter(
        "included_company_keywords", request, json=True
    )
    excluded_company_keywords = get_request_parameter(
        "excluded_company_keywords", request, json=True
    )
    included_education_keywords = get_request_parameter(
        "included_education_keywords", request, json=True
    )
    excluded_education_keywords = get_request_parameter(
        "excluded_education_keywords", request, json=True
    )
    included_bio_keywords = get_request_parameter(
        "included_bio_keywords", request, json=True
    )
    excluded_bio_keywords = get_request_parameter(
        "excluded_bio_keywords", request, json=True
    )
    included_location_keywords = get_request_parameter(
        "included_location_keywords", request, json=True
    )
    excluded_location_keywords = get_request_parameter(
        "excluded_location_keywords", request, json=True
    )
    included_skills_keywords = get_request_parameter(
        "included_skills_keywords", request, json=True
    )
    excluded_skills_keywords = get_request_parameter(
        "excluded_skills_keywords", request, json=True
    )
    years_of_experience_start = get_request_parameter(
        "years_of_experience_start", request, json=True
    )
    years_of_experience_end = get_request_parameter(
        "years_of_experience_end", request, json=True
    )

    prospects: list[dict] = find_prospects_by_segment_filters(
        client_sdr_id=client_sdr_id,
        segment_ids=segment_ids,
        included_title_keywords=included_title_keywords,
        excluded_title_keywords=excluded_title_keywords,
        included_seniority_keywords=included_seniority_keywords,
        excluded_seniority_keywords=excluded_seniority_keywords,
        included_company_keywords=included_company_keywords,
        excluded_company_keywords=excluded_company_keywords,
        included_education_keywords=included_education_keywords,
        excluded_education_keywords=excluded_education_keywords,
        included_bio_keywords=included_bio_keywords,
        excluded_bio_keywords=excluded_bio_keywords,
        included_location_keywords=included_location_keywords,
        excluded_location_keywords=excluded_location_keywords,
        included_skills_keywords=included_skills_keywords,
        excluded_skills_keywords=excluded_skills_keywords,
        years_of_experience_start=years_of_experience_start,
        years_of_experience_end=years_of_experience_end,
    )

    return jsonify({"prospects": prospects, "num_prospects": len(prospects)}), 200


@SEGMENT_BLUEPRINT.route("/extract_sales_nav_titles", methods=["POST"])
@require_user
def extract_sales_nav_titles(client_sdr_id: int):
    sales_nav_url = get_request_parameter(
        "sales_nav_url", request, json=True, required=True
    )

    data: dict = extract_data_from_sales_navigator_link(
        sales_nav_url=sales_nav_url,
    )

    return jsonify(data), 200


@SEGMENT_BLUEPRINT.route("/wipe_segment", methods=["POST"])
@require_user
def wipe_segment(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)

    segment: Segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()
    if not segment:
        return "Segment not found", 404

    success, msg = wipe_segment_ids_from_prospects_in_segment(segment_id=segment_id)
    if success:
        return msg, 200

    return "Failed", 400
