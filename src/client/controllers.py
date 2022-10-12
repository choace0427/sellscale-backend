from flask import Blueprint, request, jsonify
from src.client.models import ClientArchetype
from src.client.services import (
    create_client,
    create_client_archetype,
    create_client_sdr,
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

    ca: object = create_client_archetype(
        client_id=client_id, archetype=archetype, filters=filters
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
