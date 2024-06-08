from flask import Blueprint, request, jsonify
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.client.models import ClientTeamMessage, ClientSDR, db

TEAM_MESSAGES_BLUEPRINT = Blueprint("team_messages", __name__)

@TEAM_MESSAGES_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_all_team_messages(client_sdr_id: int):
    """Gets all team messages for a client SDR with pagination using offset and limit"""
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 10, type=int)
    
    client_sdr = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return jsonify({"message": "Client SDR not found"}), 404
    
    client_id = client_sdr.client_id
    
    team_messages_query = ClientTeamMessage.query.filter_by(client_id=client_id).offset(offset).limit(limit)
    team_messages = team_messages_query.all()
    total_items = ClientTeamMessage.query.filter_by(client_id=client_id).count()
    
    return (
        jsonify(
            {
                "message": "Success",
                "data": [message.to_dict() for message in team_messages],
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "total_items": total_items,
                },
            }
        ),
        200,
    )
@TEAM_MESSAGES_BLUEPRINT.route("/<int:message_id>", methods=["GET"])
@require_user
def get_team_message(client_sdr_id: int, message_id: int):
    """Gets a specific team message by ID"""
    team_message = ClientTeamMessage.query.filter_by(client_sdr_id=client_sdr_id, id=message_id).first()
    if not team_message:
        return (
            jsonify(
                {
                    "message": "Team message not found",
                }
            ),
            404,
        )
    return (
        jsonify(
            {
                "message": "Success",
                "data": team_message.to_dict(),
            }
        ),
        200,
    )

@TEAM_MESSAGES_BLUEPRINT.route("/", methods=["POST"])
@require_user
def post_team_message(client_sdr_id: int):
    """Creates a new team message"""
    client_id = get_request_parameter("client_id", request, json=True, required=True, parameter_type=int)
    message = get_request_parameter("message", request, json=True, required=True, parameter_type=str)
    message_type = get_request_parameter("message_type", request, json=True, required=True, parameter_type=str)

    new_message = ClientTeamMessage(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        message=message,
        message_type=message_type,
    )

    db.session.add(new_message)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Success",
                "data": new_message.to_dict(),
            }
        ),
        201,
    )

@TEAM_MESSAGES_BLUEPRINT.route("/<int:message_id>", methods=["PUT"])
@require_user
def update_team_message(client_sdr_id: int, message_id: int):
    """Updates an existing team message"""
    team_message = ClientTeamMessage.query.filter_by(client_sdr_id=client_sdr_id, id=message_id).first()
    if not team_message:
        return (
            jsonify(
                {
                    "message": "Team message not found",
                }
            ),
            404,
        )

    message = get_request_parameter("message", request, json=True, required=False, parameter_type=str)
    message_type = get_request_parameter("message_type", request, json=True, required=False, parameter_type=str)

    if message:
        team_message.message = message
    if message_type:
        team_message.message_type = message_type

    db.session.commit()

    return (
        jsonify(
            {
                "message": "Success",
                "data": team_message.to_dict(),
            }
        ),
        200,
    )

@TEAM_MESSAGES_BLUEPRINT.route("/<int:message_id>", methods=["DELETE"])
@require_user
def delete_team_message(client_sdr_id: int, message_id: int):
    """Deletes a team message"""
    team_message = ClientTeamMessage.query.filter_by(client_sdr_id=client_sdr_id, id=message_id).first()
    if not team_message:
        return (
            jsonify(
                {
                    "message": "Team message not found",
                }
            ),
            404,
        )

    db.session.delete(team_message)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Success",
            }
        ),
        200,
    )
