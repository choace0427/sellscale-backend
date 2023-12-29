from flask import Blueprint, jsonify, request
from src.ai_requests.models import AIRequest
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.ai_requests.services import create_ai_requests

AI_REQUESTS = Blueprint("ai_requests", __name__)


@AI_REQUESTS.route("/")
def index():
    return "OK", 200

@AI_REQUESTS.route("/user", methods=["GET"])
@require_user
def get_ai_requests(client_sdr_id: int):
    """
    Retrieves all AI Requests for a specific client SDR ID.
    """
    try:
        # Finds all AIRequests related to the user
        ai_requests = AIRequest.query.filter(AIRequest.client_sdr_id == client_sdr_id).all()
        ai_requests_data = [{
            "id": req.id,
            "client_sdr_id": req.client_sdr_id,
            "title": req.title,
            "description": req.description,
            "percent_complete": req.percent_complete,
            "creation_date": req.creation_date.isoformat(),
            "due_date": req.due_date.isoformat(),
            "status": req.status.value,
            "message": req.message
        } for req in ai_requests]

        return jsonify({"message": "Success", "data": ai_requests_data}), 200
    except Exception as e:
        print(f"Error fetching AI requests: {e}")
        return jsonify({"message": "Error fetching AI requests", "data": [], "error": str(e)}), 500

@AI_REQUESTS.route("/feedback", methods=["POST"])
@require_user
def post_ai_request(client_sdr_id: int):
    ai_request = get_request_parameter(
        "content", request, json=True, required=True, parameter_type=str
    )

    # Uses the service function to create the AI Request object
    new_request = create_ai_requests(client_sdr_id, ai_request)

    # If the new_request object exists, assumes it's successful
    if new_request:
        return jsonify({"status": "success", "message": "AI request created successfully", "request_id": new_request.id}), 201
    else:
        return jsonify({"status": "error", "message": "Failed to create AI request"}), 500
