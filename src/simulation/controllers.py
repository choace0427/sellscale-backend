from typing import List
from flask import Blueprint, request, jsonify
from src.simulation.models import SimulationType
from src.simulation.services import (
    send_li_convo_message,
    create_simulation,
    get_sim_li_convo_history,
    generate_sim_li_convo_init_msg,
    generate_sim_li_convo_response,
    update_sim_li_convo,
)
from src.simulation.models import Simulation
from src.prospecting.models import Prospect
from src.li_conversation.models import LinkedInConvoMessage
from app import db
import os
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter

SIMULATION_BLUEPRINT = Blueprint("simulation", __name__)


@SIMULATION_BLUEPRINT.route("/li_convo", methods=["POST"])
@require_user
def post_li_convo_create(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    simulation_id = create_simulation(
        client_sdr_id, archetype_id, prospect_id, SimulationType.LI_CONVERSATION
    )

    return jsonify({"message": "Success", "data": simulation_id}), 201


@SIMULATION_BLUEPRINT.route("/li_convo", methods=["GET"])
@require_user
def get_li_convo(client_sdr_id: int):
    simulation_id = get_request_parameter(
        "simulation_id", request, json=False, required=False, parameter_type=int
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=False, parameter_type=int
    )

    if simulation_id:
        simulation: Simulation = Simulation.query.get(simulation_id)
    elif prospect_id:
        simulation: Simulation = (
            Simulation.query.filter_by(prospect_id=prospect_id)
            .order_by(Simulation.created_at.desc())
            .first()
        )

        if not simulation:
            prospect: Prospect = Prospect.query.get(prospect_id)
            archetype_id = prospect.archetype_id
            simulation_id = create_simulation(
                client_sdr_id, archetype_id, prospect_id, SimulationType.LI_CONVERSATION
            )
            simulation = Simulation.query.get(simulation_id)
    else:
        return jsonify({"message": "Invalid request"}), 400

    if not simulation or simulation.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Invalid simulation"}), 400

    if simulation.type.value != "LI_CONVERSATION":
        return jsonify({"message": "Simulation is not of a LinkedIn conversation"}), 400

    msgs: List[LinkedInConvoMessage] = get_sim_li_convo_history(simulation.id, True)

    return (
        jsonify(
            {
                "message": "Success",
                "data": {
                    "simulation": simulation.to_dict(),
                    "messages": [msg.to_dict() for msg in msgs],
                },
            }
        ),
        200,
    )


@SIMULATION_BLUEPRINT.route("/li_convo/send_message", methods=["POST"])
@require_user
def post_li_convo_send_message(client_sdr_id: int):
    simulation_id = get_request_parameter(
        "simulation_id", request, json=True, required=True, parameter_type=int
    )
    message = get_request_parameter(
        "message", request, json=True, required=True, parameter_type=str
    )

    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation or simulation.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Invalid simulation"}), 400

    if simulation.type.value != "LI_CONVERSATION":
        return jsonify({"message": "Simulation is not of a LinkedIn conversation"}), 400

    prospect: Prospect = Prospect.query.get(simulation.prospect_id)

    success = send_li_convo_message(
        simulation_id=simulation_id,
        message=LinkedInConvoMessage(
            message=message,
            connection_degree="1st",
            author=prospect.full_name,
        ),
    )

    if not success:
        return jsonify({"message": "Failed to send message"}), 400

    return jsonify({"message": "Success"}), 200


@SIMULATION_BLUEPRINT.route("/li_convo/generate_initial_message", methods=["POST"])
@require_user
def post_li_convo_generate_initial_message(client_sdr_id: int):
    simulation_id = get_request_parameter(
        "simulation_id", request, json=True, required=True, parameter_type=int
    )
    template_id = get_request_parameter(
        "template_id", request, json=True, required=False, parameter_type=int
    )

    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation or simulation.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Invalid simulation"}), 400

    if simulation.type.value != "LI_CONVERSATION":
        return jsonify({"message": "Simulation is not of a LinkedIn conversation"}), 400

    tries = 0
    success = False
    error_msg = ""
    while tries < 3:
        tries = tries + 1
        try:
            success = generate_sim_li_convo_init_msg(
                simulation_id=simulation_id, template_id=template_id
            )
            if success:
                break
        except Exception as e:
            print("Failed to generate initial message for simulation: ", str(e))
            error_msg = str(e)
            raise e
            continue

    if not success:
        return (
            jsonify(
                {"message": "Failed to generate initial message", "error": error_msg}
            ),
            400,
        )

    return jsonify({"message": "Success"}), 200


@SIMULATION_BLUEPRINT.route("/li_convo/generate_response", methods=["POST"])
@require_user
def post_li_convo_generate_response(client_sdr_id: int):
    simulation_id = get_request_parameter(
        "simulation_id", request, json=True, required=True, parameter_type=int
    )

    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation or simulation.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Invalid simulation"}), 400

    if simulation.type.value != "LI_CONVERSATION":
        return jsonify({"message": "Simulation is not of a LinkedIn conversation"}), 400

    success, status_msg = generate_sim_li_convo_response(simulation_id=simulation_id)

    if not success:
        return (
            jsonify(
                {"message": f"Failed to generate response message: '{status_msg}'"}
            ),
            400,
        )

    return jsonify({"message": "Success"}), 200


@SIMULATION_BLUEPRINT.route("/li_convo/update", methods=["POST"])
@require_user
def post_li_convo_update(client_sdr_id: int):
    simulation_id = get_request_parameter(
        "simulation_id", request, json=True, required=True, parameter_type=int
    )

    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation or simulation.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Invalid simulation"}), 400

    if simulation.type.value != "LI_CONVERSATION":
        return jsonify({"message": "Simulation is not of a LinkedIn conversation"}), 400

    success = update_sim_li_convo(simulation_id=simulation_id)

    if not success:
        return jsonify({"message": "Failed to update simulation"}), 400

    return jsonify({"message": "Success"}), 200
