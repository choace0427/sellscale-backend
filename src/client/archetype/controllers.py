from flask import Blueprint, jsonify, request

from src.authentication.decorators import require_user
from src.client.archetype.services_client_archetype import bulk_action_move_prospects_to_archetype, bulk_action_withdraw_prospect_invitations
from src.client.models import ClientArchetype, ClientSDR
from src.utils.request_helpers import get_request_parameter


CLIENT_ARCHETYPE_BLUEPRINT = Blueprint("client/archetype", __name__)


@CLIENT_ARCHETYPE_BLUEPRINT.route("/bulk_action/move", methods=["POST"])
@require_user
def post_archetype_bulk_action_move_prospects(client_sdr_id: int):
    target_archetype_id = get_request_parameter(
        "target_archetype_id", request, json=True, required=True, parameter_type=int
    )
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )

    if len(prospect_ids) > 100:
        return (
            jsonify({"status": "error", "message": "Too many prospects. Limit 100."}),
            400,
        )

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    target_archetype: ClientArchetype = ClientArchetype.query.get(target_archetype_id)
    if not target_archetype or sdr.id != target_archetype.client_sdr_id:
        return jsonify({"status": "error", "message": "Invalid target archetype"}), 400

    success = bulk_action_move_prospects_to_archetype(
        client_sdr_id=client_sdr_id,
        target_archetype_id=target_archetype_id,
        prospect_ids=prospect_ids,
    )
    if success:
        return (
            jsonify({"status": "success", "data": {"message": "Moved prospects"}}),
            200,
        )

    return jsonify({"status": "error", "message": "Failed to move prospects"}), 400


@CLIENT_ARCHETYPE_BLUEPRINT.route("/bulk_action/withdraw", methods=["POST"])
@require_user
def post_archetype_bulk_action_withdraw_invitations(client_sdr_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )

    success, _ = bulk_action_withdraw_prospect_invitations(
        client_sdr_id=client_sdr_id,
        prospect_ids=prospect_ids,
    )

    if not success:
        return (
            jsonify({"status": "error", "message": "Failed to withdraw invitations"}),
            400,
        )

    return jsonify({"status": "success"}), 200
