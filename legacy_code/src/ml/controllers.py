@ML_BLUEPRINT.route("/generate_sequence_draft", methods=["POST"])
@require_user
def get_sequence_draft_endpoint(client_sdr_id: int):
    """Gets a sequence draft for a given value prop"""
    value_props = get_request_parameter(
        "value_props", request, json=True, required=True, parameter_type=list
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": "Archetype not found"}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Archetype does not belong to this user"}), 401

    try:
        result = get_sequence_draft(value_props, client_sdr_id, archetype_id)
        if not result:
            return jsonify({"message": "Generation rejected, please try again."}), 424
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

    return jsonify({"message": "Success", "data": result}), 200