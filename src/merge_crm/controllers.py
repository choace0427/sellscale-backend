from flask import Blueprint, jsonify, request

from src.authentication.decorators import require_user
from src.merge_crm.services import (
    create_link_token,
    create_test_account,
    delete_integration,
    get_integration,
    get_operation_availability,
    retrieve_account_token,
    update_crm_sync,
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

    return jsonify({"success": True})


@MERGE_CRM_BLUEPRINT.route("/test_account", methods=["POST"])
@require_user
def make_test_account(client_sdr_id: int):
    create_test_account(client_sdr_id=client_sdr_id)
    return jsonify({"success": True})


@MERGE_CRM_BLUEPRINT.route("/update_crm_sync", methods=["PUT"])
@require_user
def put_update_crm_sync_endpoint(client_sdr_id: int):
    sync_type = get_request_parameter("sync_type", request, json=True, required=False)
    status_mapping = get_request_parameter(
        "status_mapping", request, json=True, required=False
    )
    event_handlers = get_request_parameter(
        "event_handlers", request, json=True, required=False
    )

    result = update_crm_sync(
        client_sdr_id=client_sdr_id,
        sync_type=sync_type,
        status_mapping=status_mapping,
        event_handlers=event_handlers,
    )

    return jsonify({"success": True, "data": result})


@MERGE_CRM_BLUEPRINT.route("/crm_sync", methods=["GET"])
@require_user
def get_crm_sync_endpoint(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=sdr.client_id
    ).first()

    result = client_sync_crm.to_dict() if client_sync_crm else None

    return jsonify({"success": True, "data": result})


@MERGE_CRM_BLUEPRINT.route("/crm_operation_available", methods=["GET"])
@require_user
def get_crm_operation_available_endpoint(client_sdr_id: int):
    operation = get_request_parameter("operation", request, json=False, required=True)

    available = get_operation_availability(
        client_sdr_id=client_sdr_id, operation_name=operation
    )

    return jsonify(
        {"success": True, "data": {"operation": operation, "available": available}}
    )


@MERGE_CRM_BLUEPRINT.route("/create_opportunity", methods=["POST"])
@require_user
def create_opportunity(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )

    success, msg = create_opportunity_from_prospect_id(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id
    )
    return jsonify({"success": success, "message": msg}), 200 if success else 400
