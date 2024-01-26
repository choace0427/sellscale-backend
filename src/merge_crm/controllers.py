from flask import Blueprint, jsonify, request

from src.authentication.decorators import require_user
from src.merge_crm.services import (
    create_link_token,
    create_test_account,
    delete_account_token,
    get_integrations,
    retrieve_account_token,
)
from src.utils.request_helpers import get_request_parameter


MERGE_CRM_BLUEPRINT = Blueprint("merge_crm", __name__)


@MERGE_CRM_BLUEPRINT.route("/link", methods=["POST"])
@require_user
def link(client_sdr_id: int):
    token = create_link_token(client_sdr_id=client_sdr_id)

    return jsonify({"link_token": token})


@MERGE_CRM_BLUEPRINT.route("/connect_link", methods=["POST"])
@require_user
def connect_link(client_sdr_id: int):
    public_token = get_request_parameter(
        "public_token", request, json=True, required=True
    )

    account_token = retrieve_account_token(
        client_sdr_id=client_sdr_id, public_token=public_token
    )

    return jsonify({"account_token": account_token})


@MERGE_CRM_BLUEPRINT.route("/integrations", methods=["GET"])
@require_user
def get_integrations_endpoint(client_sdr_id: int):
    integrations = get_integrations(client_sdr_id=client_sdr_id)

    return jsonify({"integrations": integrations})


@MERGE_CRM_BLUEPRINT.route("/link", methods=["DELETE"])
@require_user
def delete_link(client_sdr_id: int):
    delete_account_token(client_sdr_id=client_sdr_id)

    return jsonify({"success": True})


@MERGE_CRM_BLUEPRINT.route("/test_account", methods=["POST"])
@require_user
def make_test_account(client_sdr_id: int):
    create_test_account(client_sdr_id=client_sdr_id)
    return jsonify({"success": True})
