from flask import Blueprint, request, jsonify

from src.authentication.decorators import require_user
from src.strategies.services import create_strategy, create_strategy_client_archetype_mapping, delete_strategy_archetype_mapping, edit_strategy, get_all_strategies, get_strategy_dict

from src.utils.request_helpers import get_request_parameter


STRATEGIES_BLUEPRINT = Blueprint("strategies", __name__)


@STRATEGIES_BLUEPRINT.route("/echo", methods=["GET"])
@require_user
def get_all_subscriptions(client_sdr_id: int):
    return 'OK', 200

@STRATEGIES_BLUEPRINT.route("/create", methods=["POST"])
@require_user
def post_create_strategy(client_sdr_id: int):
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=True, parameter_type=str
    )
    client_archetype_ids = get_request_parameter(
        "client_archetype_ids", request, json=True, required=True, parameter_type=list
    )

    start_date = get_request_parameter(
        "start_date", request, json=True, required=False, parameter_type=str
    )

    end_date = get_request_parameter(
        "end_date", request, json=True, required=False, parameter_type=str
    )

    strategy = create_strategy(
        client_sdr_id=client_sdr_id,
        name=name,
        description=description,
        client_archetype_ids=client_archetype_ids,
        start_date=start_date,
        end_date=end_date,
    )

    return jsonify(strategy), 201

@STRATEGIES_BLUEPRINT.route("/<int:strategy_id>", methods=["GET"])
@require_user
def get_strategy(client_sdr_id: int, strategy_id: int):
    strategy = get_strategy_dict(strategy_id=strategy_id)
    return jsonify(strategy), 200

@STRATEGIES_BLUEPRINT.route("/<int:strategy_id>/update", methods=["PATCH"])
@require_user
def patch_update_strategy(client_sdr_id: int, strategy_id: int):
    new_title = get_request_parameter(
        "new_title", request, json=True, required=False, parameter_type=str
    )
    new_description = get_request_parameter(
        "new_description", request, json=True, required=False, parameter_type=str
    )
    new_status = get_request_parameter(
        "new_status", request, json=True, required=False, parameter_type=str
    )
    new_archetypes = get_request_parameter(
        "new_archetypes", request, json=True, required=False, parameter_type=list
    )

    start_date = get_request_parameter(
        "start_date", request, json=True, required=False, parameter_type=str
    )

    end_date = get_request_parameter(
        "end_date", request, json=True, required=False, parameter_type=str
    )

    strategy = edit_strategy(
        client_sdr_id=client_sdr_id,
        strategy_id=strategy_id,
        new_title=new_title,
        new_description=new_description,
        new_status=new_status,
        new_archetypes=new_archetypes,
        new_start_date=start_date,
        new_end_date=end_date,
    )

    return jsonify(strategy), 200

@STRATEGIES_BLUEPRINT.route("/<int:strategy_id>/add_archetype_mapping", methods=["POST"])
@require_user
def post_add_archetype_mapping(client_sdr_id: int, strategy_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )

    strategy = create_strategy_client_archetype_mapping(
        client_sdr_id=client_sdr_id,
        strategy_id=strategy_id,
        client_archetype_id=client_archetype_id,
    )

    return jsonify(strategy), 201

@STRATEGIES_BLUEPRINT.route("/<int:strategy_id>/remove_archetype_mapping", methods=["DELETE"])
@require_user
def delete_remove_archetype_mapping(client_sdr_id: int, strategy_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )

    success = delete_strategy_archetype_mapping(
        client_sdr_id=client_sdr_id,
        strategy_id=strategy_id,
        client_archetype_id=client_archetype_id,
    )

    if not success:
        return "Mapping not found", 404
    
    return "Mapping deleted", 200

@STRATEGIES_BLUEPRINT.route("/get_all", methods=["GET"])
@require_user
def all_strategies(client_sdr_id: int):
    all_strats = get_all_strategies(client_sdr_id=client_sdr_id)
    return jsonify(all_strats), 200