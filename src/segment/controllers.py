from flask import Blueprint, request
from src.authentication.decorators import require_user
from src.prospecting.models import Prospect
from src.segment.models import Segment
from src.segment.services import (
    add_prospects_to_segment,
    create_new_segment,
    delete_segment,
    get_segments_for_sdr,
    update_segment,
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
