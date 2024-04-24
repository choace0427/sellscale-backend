from app import db

from flask import Blueprint, jsonify, request
from src.utils.request_helpers import get_request_parameter

QUESTION_ENRICHMENT_BLUEPRINT = Blueprint("question_enrichment", __name__)


@QUESTION_ENRICHMENT_BLUEPRINT.route("/create_request", methods=["POST"])
def create_enrichment_request():
    from src.prospecting.question_enrichment.services import (
        create_question_enrichment_request,
    )

    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )
    question = get_request_parameter("question", request, json=True, required=True)

    request = create_question_enrichment_request(
        prospect_ids=prospect_ids, question=question
    )

    if request is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to create question enrichment request",
                }
            ),
            500,
        )

    return jsonify({"success": True, "request": request.to_dict()}), 200
