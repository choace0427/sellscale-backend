from flask import Blueprint, jsonify, request

from src.authentication.decorators import require_user
from src.client.sdr.services_client_sdr import get_active_sdrs
from src.merge_crm.services import (
    create_link_token,
    create_test_account,
    delete_integration,
    get_client_sync_crm,
    get_crm_stages,
    get_crm_users,
    get_integration,
    get_operation_availability,
    retrieve_account_token,
    sync_sdr_to_crm_user,
    sync_sellscale_to_crm_stages,
)
from src.utils.request_helpers import get_request_parameter
from model_import import ClientSDR
from src.merge_crm.models import ClientSyncCRM
from src.merge_crm.services import create_opportunity_from_prospect_id

MERGE_CRM_BLUEPRINT = Blueprint("merge_crm", __name__)


###############################
#   INTEGRATION CONTROLLERS   #
###############################


@MERGE_CRM_BLUEPRINT.route("/link_token", methods=["GET"])
@require_user
def get_link_token(client_sdr_id: int):
    success, link_token = create_link_token(client_sdr_id=client_sdr_id)
    if not success:
        return (
            jsonify({"status": "error", "message": "Failed to create link token"}),
            400,
        )

    return jsonify({"status": "success", "data": {"link_token": link_token}})


@MERGE_CRM_BLUEPRINT.route("/account_token", methods=["POST"])
@require_user
def post_get_account_token(client_sdr_id: int):
    public_token = get_request_parameter(
        "public_token", request, json=True, required=True
    )

    success, account_token = retrieve_account_token(
        client_sdr_id=client_sdr_id, public_token=public_token
    )
    if not success:
        return (
            jsonify(
                {"status": "error", "message": "Failed to retrieve an account token"}
            ),
            400,
        )

    return jsonify(
        {
            "status": "success",
            "data": {"account_token": "Account Token Retrieved and Stored"},
        }
    )


@MERGE_CRM_BLUEPRINT.route("/integration", methods=["GET"])
@require_user
def get_integration_endpoint(client_sdr_id: int):
    integration = get_integration(client_sdr_id=client_sdr_id)

    return jsonify({"integration": integration})


@MERGE_CRM_BLUEPRINT.route("/integration", methods=["DELETE"])
@require_user
def delete_integration_endpoint(client_sdr_id: int):
    success, message = delete_integration(client_sdr_id=client_sdr_id)
    if not success:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({"status": "success"})


@MERGE_CRM_BLUEPRINT.route("/test_account", methods=["POST"])
@require_user
def make_test_account(client_sdr_id: int):
    create_test_account(client_sdr_id=client_sdr_id)
    return jsonify({"status": "success"})


###############################
#    CRM SYNC CONTROLLERS     #
###############################


@MERGE_CRM_BLUEPRINT.route("/crm_sync", methods=["GET"])
@require_user
def get_crm_sync_endpoint(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=sdr.client_id
    ).first()

    result = client_sync_crm.to_dict() if client_sync_crm else None

    return jsonify({"status": "success", "data": result})


@MERGE_CRM_BLUEPRINT.route("/users", methods=["GET"])
@require_user
def get_crm_users_endpoint(client_sdr_id: int):
    users = get_crm_users(client_sdr_id=client_sdr_id)
    sdrs = get_active_sdrs(client_sdr_id=client_sdr_id)

    return jsonify({"status": "success", "data": {"users": users, "sdrs": sdrs}})


@MERGE_CRM_BLUEPRINT.route("/users/sync/sdr", methods=["POST"])
@require_user
def post_sync_sdr_to_crm_user(client_sdr_id: int):
    merge_user_id = (
        get_request_parameter("merge_user_id", request, json=True, required=False)
        or None
    )

    success = sync_sdr_to_crm_user(
        client_sdr_id=client_sdr_id, merge_user_id=merge_user_id
    )
    if not success:
        return jsonify({"status": "error", "message": "Failed to sync user"}), 400

    return jsonify({"status": "success"})


@MERGE_CRM_BLUEPRINT.route("/stages", methods=["GET"])
@require_user
def get_crm_stages_endpoint(client_sdr_id: int):
    stages = get_crm_stages(client_sdr_id=client_sdr_id)
    current_mapping = get_client_sync_crm(client_sdr_id).get("status_mapping")

    return jsonify(
        {"status": "success", "data": {"stages": stages, "mapping": current_mapping}}
    )


@MERGE_CRM_BLUEPRINT.route("/stages/sync", methods=["POST"])
@require_user
def post_sync_stages(client_sdr_id: int):
    stage_mapping = (
        get_request_parameter("stage_mapping", request, json=True, required=False)
    ) or {}

    success = sync_sellscale_to_crm_stages(
        client_sdr_id=client_sdr_id, stage_mapping=stage_mapping
    )
    if not success:
        return jsonify({"status": "error", "message": "Failed to sync stages"}), 400

    return jsonify({"status": "success"})


# TODO: Deprecate
@MERGE_CRM_BLUEPRINT.route("/crm_operation_available", methods=["GET"])
@require_user
def get_crm_operation_available_endpoint(client_sdr_id: int):
    operation = get_request_parameter("operation", request, json=False, required=True)

    available = get_operation_availability(
        client_sdr_id=client_sdr_id, operation_name=operation
    )

    return jsonify(
        {"status": "success", "data": {"operation": operation, "available": available}}
    )


@MERGE_CRM_BLUEPRINT.route("/opportunity/create", methods=["POST"])
@require_user
def create_opportunity(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )

    success, msg = create_opportunity_from_prospect_id(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id
    )
    return jsonify({"success": success, "message": msg}), 200 if success else 400
