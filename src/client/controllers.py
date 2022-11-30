from flask import Blueprint, request, jsonify
from src.client.models import ClientArchetype
from src.client.services import (
    create_client,
    create_client_archetype,
    create_client_sdr,
    rename_archetype,
    toggle_archetype_active,
    update_client_sdr_email,
    update_client_sdr_scheduling_link,
)

from src.utils.request_helpers import get_request_parameter

CLIENT_BLUEPRINT = Blueprint("client", __name__)


@CLIENT_BLUEPRINT.route("/")
def index():
    return "OK", 200


@CLIENT_BLUEPRINT.route("/", methods=["POST"])
def create():
    company = get_request_parameter("company", request, json=True, required=True)
    contact_name = get_request_parameter(
        "contact_name", request, json=True, required=True
    )
    contact_email = get_request_parameter(
        "contact_email", request, json=True, required=True
    )

    resp = create_client(
        company=company, contact_name=contact_name, contact_email=contact_email
    )

    return jsonify(resp)


@CLIENT_BLUEPRINT.route("/archetype", methods=["POST"])
def create_archetype():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    archetype = get_request_parameter("archetype", request, json=True, required=True)
    filters = get_request_parameter("filters", request, json=True, required=False)

    base_archetype_id = get_request_parameter(
        "base_archetype_id", request, json=True, required=False
    )

    ca: object = create_client_archetype(
        client_id=client_id,
        archetype=archetype,
        filters=filters,
        base_archetype_id=base_archetype_id,
    )
    if not ca:
        return "Client not found", 404

    return ca


@CLIENT_BLUEPRINT.route("/sdr", methods=["POST"])
def create_sdr():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    name = get_request_parameter("name", request, json=True, required=True)
    email = get_request_parameter("email", request, json=True, required=True)

    resp = create_client_sdr(client_id=client_id, name=name, email=email)
    if not resp:
        return "Client not found", 404

    return resp


@CLIENT_BLUEPRINT.route("/reset_client_sdr_auth_token", methods=["POST"])
def reset_client_sdr_auth_token():
    from src.client.services import reset_client_sdr_sight_auth_token

    sdr_id = get_request_parameter("client_sdr_id", request, json=True, required=True)

    resp = reset_client_sdr_sight_auth_token(client_sdr_id=sdr_id)
    if not resp:
        return "Client not found", 404

    return jsonify(resp)


@CLIENT_BLUEPRINT.route("/archetype", methods=["PATCH"])
def update_archetype_name():
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    new_name = get_request_parameter("new_name", request, json=True, required=True)

    success = rename_archetype(
        client_archetype_id=client_archetype_id, new_name=new_name
    )

    if not success:
        return "Failed to update name", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/archetype/toggle_active", methods=["PATCH"])
def patch_toggle_archetype_active():
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )

    success = toggle_archetype_active(archetype_id=client_archetype_id)

    if not success:
        return "Failed to update active", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/update_scheduling_link", methods=["PATCH"])
def patch_update_scheduling_link():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    scheduling_link = get_request_parameter(
        "scheduling_link", request, json=True, required=True
    )

    success = update_client_sdr_scheduling_link(
        client_sdr_id=client_sdr_id, scheduling_link=scheduling_link
    )

    if not success:
        return "Failed to update scheduling link", 404
    return "OK", 200


@CLIENT_BLUEPRINT.route("/sdr/update_email", methods=["PATCH"])
def patch_update_sdr_email():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    email = get_request_parameter("email", request, json=True, required=True)

    success = update_client_sdr_email(client_sdr_id=client_sdr_id, email=email)

    if not success:
        return "Failed to update email", 404
    return "OK", 200
