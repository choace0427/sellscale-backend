from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.client.models import ClientSDR
from src.prospecting.models import ProspectUploadSource
from src.prospecting.upload.services import (
    create_prospect_from_linkedin_link,
    get_prospect_upload_history,
    get_prospect_upload_history_details,
)
from src.prospecting.upload.services import (
    create_prospect_from_prospect_upload_row,
    create_prospect_upload_history,
    populate_prospect_uploads_from_linkedin_link,
)
from src.segment.services import get_base_segment_for_archetype
from src.utils.request_helpers import get_request_parameter


PROSPECTING_UPLOAD_BLUEPRINT = Blueprint("prospect/upload", __name__)


@PROSPECTING_UPLOAD_BLUEPRINT.route("/history", methods=["GET"])
@require_user
def get_prospect_upload_history_endpoint(client_sdr_id: int):
    """Gets the Prospect Upload History for a Client SDR."""
    offset = get_request_parameter("offset", request, required=False, default_value=0)
    limit = get_request_parameter("limit", request, required=False, default_value=10)

    history = get_prospect_upload_history(
        client_sdr_id=client_sdr_id, offset=offset, limit=limit
    )

    return jsonify({"status": "success", "data": {"history": history}}), 200


@PROSPECTING_UPLOAD_BLUEPRINT.route(
    "/history/<int:history_id>/details", methods=["GET"]
)
@require_user
def get_prospect_upload_history_details_endpoint(client_sdr_id: int, history_id: int):
    """Gets the Prospect Upload History Details for a Client SDR."""
    details = get_prospect_upload_history_details(upload_id=history_id)

    return jsonify({"status": "success", "data": {"details": details}}), 200


@PROSPECTING_UPLOAD_BLUEPRINT.route("/linkedin_link", methods=["POST"])
@require_user
def post_upload_prospect_from_linkedin_link(client_sdr_id: int):
    """Uploads a Prospect from a single LinkedIn Link."""
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    segment_id = get_request_parameter("segment_id", request, json=True, required=False)
    url = get_request_parameter("url", request, json=True, required=True)
    live = get_request_parameter(
        "live", request, json=True, required=False, default=False
    )
    is_lookalike_profile = (
        get_request_parameter(
            "is_lookalike_profile", request, json=True, required=False
        )
        or False
    )
    custom_data = get_request_parameter(
        "custom_data", request, json=True, required=False, default={}
    )

    # Create the Upload History object
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not segment_id:
        segment_id = get_base_segment_for_archetype(archetype_id=archetype_id)
    upload_history_id = create_prospect_upload_history(
        client_id=sdr.client_id,
        sdr_id=client_sdr_id,
        upload_source=ProspectUploadSource.LINKEDIN_LINK,
        raw_data=[
            {
                "linkedin_url": url,
                "custom_data": custom_data,
                "is_lookalike_profile": is_lookalike_profile,
            }
        ],
        client_segment_id=segment_id,
        client_archetype_id=archetype_id,
    )

    # Populate the Prospect Uploads
    upload_id = populate_prospect_uploads_from_linkedin_link(
        upload_history_id=upload_history_id
    )

    # Create the Prospect either synchronously or asynchronously
    if live:
        success, prospect_id = create_prospect_from_linkedin_link(
            prospect_upload_id=upload_id,
            segment_id=segment_id,
        )
        if success:
            return (
                jsonify({"status": "success", "data": {"prospect_id": prospect_id}}),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "This Prospect already exists elsewhere in your organization",
                    }
                ),
                500,
            )
    else:
        create_prospect_from_linkedin_link.delay(
            prospect_upload_id=upload_id,
            segment_id=segment_id,
        )
        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "message": "Successfully queued this Prospect to be created."
                    },
                }
            ),
            200,
        )
