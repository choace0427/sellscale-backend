import string
from sqlalchemy import cast, String
from flask import Blueprint, jsonify, request
from src.ai_requests.models import AIRequest, AIRequestStatus
from model_import import ClientSDR, Client
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.ai_requests.services import create_ai_requests, update_ai_requests

AI_REQUESTS = Blueprint("ai_requests", __name__)


@AI_REQUESTS.route("/")
def index():
    return "OK", 200


@AI_REQUESTS.route("/all", methods=["GET"])
def get_all_ai_requests():
    """
    Retrieves all AI Requests.
    """
    try:
        # Finds all AIRequests
        ai_requests = (
            AIRequest.query.join(ClientSDR, AIRequest.client_sdr_id == ClientSDR.id)
            .join(Client, ClientSDR.client_id == Client.id)
            .all()
        )

        ai_requests: list = (
            AIRequest.query.join(ClientSDR, AIRequest.client_sdr_id == ClientSDR.id)
            .join(Client, ClientSDR.client_id == Client.id)
            .add_columns(
                AIRequest.id,
                AIRequest.client_sdr_id,
                AIRequest.title,
                AIRequest.description,
                AIRequest.percent_complete,
                AIRequest.creation_date,
                AIRequest.due_date,
                AIRequest.status,
                AIRequest.message,
                ClientSDR.name.cast(String).label("client_sdr_name"),
                ClientSDR.auth_token.cast(String).label("client_auth_token"),
                ClientSDR.client_id,
                Client.company.cast(String).label("client_company"),
            )
            .all()
        )

        ai_requests_data = [
            {
                "id": req.id,
                "client_sdr_id": req.client_sdr_id,
                "client_sdr_name": req.client_sdr_name,
                "client_auth_token": req.client_auth_token,
                "title": req.title,
                "description": req.description,
                "percent_complete": req.percent_complete,
                "creation_date": req.creation_date.isoformat(),
                "due_date": req.due_date.isoformat(),
                "status": req.status.value,
                "message": req.message,
                "client_id": req.client_id,
                "client_company": req.client_company,
                # Add other fields from ClientSDR as needed
            }
            for req in ai_requests
        ]

        return jsonify({"message": "Success", "data": ai_requests_data}), 200
    except Exception as e:
        print(f"Error fetching AI requests: {e}")
        return (
            jsonify(
                {"message": "Error fetching AI requests", "data": [], "error": str(e)}
            ),
            500,
        )


@AI_REQUESTS.route("/user", methods=["GET"])
@require_user
def get_ai_requests(client_sdr_id: int):
    """
    Retrieves all AI Requests for a specific client SDR ID.
    """
    try:
        # Finds all AIRequests related to the user
        ai_requests = AIRequest.query.filter(
            AIRequest.client_sdr_id == client_sdr_id
        ).order_by(AIRequest.created_at.desc())
        ai_requests_data = [
            {
                "id": req.id,
                "client_sdr_id": req.client_sdr_id,
                "title": req.title,
                "description": req.description,
                "percent_complete": req.percent_complete,
                "creation_date": req.creation_date.isoformat(),
                "due_date": req.due_date.isoformat(),
                "status": req.status.value,
                "message": req.message,
            }
            for req in ai_requests
        ]

        return jsonify({"message": "Success", "data": ai_requests_data}), 200
    except Exception as e:
        print(f"Error fetching AI requests: {e}")
        return (
            jsonify(
                {"message": "Error fetching AI requests", "data": [], "error": str(e)}
            ),
            500,
        )


@AI_REQUESTS.route("/", methods=["PATCH"])
def patch_ai_request():
    ai_request_id = get_request_parameter(
        "ai_request_id", request, json=True, required=True, parameter_type=int
    )
    status = get_request_parameter(
        "status", request, json=True, required=True, parameter_type=str
    )
    minutes_worked = get_request_parameter(
        "minutes_worked", request, json=True, required=True, parameter_type=int
    )
    details = get_request_parameter(
        "details", request, json=True, required=False, parameter_type=str
    )

    # Uses the service function to create the AI Request object
    status = AIRequestStatus[status]
    update_ai_requests(ai_request_id, status, minutes_worked, details)

    if True:
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "AI request updated successfully",
                    "request_id": ai_request_id,
                }
            ),
            200,
        )
    else:
        return (
            jsonify({"status": "error", "message": "Failed to update AI request"}),
            500,
        )


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
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "AI request created successfully",
                    "request_id": new_request.id,
                }
            ),
            201,
        )
    else:
        return (
            jsonify({"status": "error", "message": "Failed to create AI request"}),
            500,
        )
