from flask import Blueprint, jsonify, request

from src.authentication.decorators import require_user
from src.client.sdr.services_client_sdr import get_active_sdrs
from src.merge_crm.services import (
    create_link_token,
    create_test_account,
    delete_integration,
    get_client_sync_crm,
    get_client_sync_crm_supported_models,
    get_crm_stages,
    get_crm_user_contacts_from_db,
    get_crm_users,
    get_integration,
    retrieve_account_token,
    save_sellscale_crm_event_handler,
    sync_sdr_to_crm_user,
    sync_sellscale_to_crm_stages,
    update_syncable_models,
    upload_prospect_to_crm,
)
from src.utils.request_helpers import get_request_parameter
from model_import import ClientSDR
from src.merge_crm.models import ClientSyncCRM

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
    supported_models = get_client_sync_crm_supported_models(client_sdr_id=client_sdr_id)
    crm_sync = get_client_sync_crm(client_sdr_id=client_sdr_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "integration": integration,
                    "supported_models": supported_models,
                    "crm_sync": crm_sync,
                },
            }
        ),
        200,
    )


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


@MERGE_CRM_BLUEPRINT.route("/crm_sync", methods=["PATCH"])
@require_user
def patch_crm_sync_endpoint(client_sdr_id: int):
    lead_sync = get_request_parameter("lead_sync", request, json=True, required=False)
    contact_sync = get_request_parameter(
        "contact_sync", request, json=True, required=False
    )
    account_sync = get_request_parameter(
        "account_sync", request, json=True, required=False
    )
    opportunity_sync = get_request_parameter(
        "opportunity_sync", request, json=True, required=False
    )

    success = update_syncable_models(
        client_sdr_id=client_sdr_id,
        lead_sync=lead_sync,
        contact_sync=contact_sync,
        account_sync=account_sync,
        opportunity_sync=opportunity_sync,
    )

    if not success:
        return (
            jsonify({"status": "error", "message": "Failed to update sync status"}),
            400,
        )

    return jsonify({"status": "success"}), 200


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
    given_client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )

    # Ensure that this SDR is permissioned to edit the given SDR
    given_client_sdr: ClientSDR = ClientSDR.query.get(given_client_sdr_id)
    if not given_client_sdr:
        return jsonify({"status": "error", "message": "Client SDR not found"}), 400
    request_client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not request_client_sdr:
        return jsonify({"status": "error", "message": "Client SDR not found"}), 400
    if request_client_sdr.client_id != given_client_sdr.client_id:
        return (
            jsonify(
                {"status": "error", "message": "You are not authorized to edit this"}
            ),
            401,
        )

    success = sync_sdr_to_crm_user(
        client_sdr_id=given_client_sdr_id, merge_user_id=merge_user_id
    )
    if not success:
        return jsonify({"status": "error", "message": "Failed to sync user"}), 400

    return jsonify({"status": "success"})


@MERGE_CRM_BLUEPRINT.route("/stages", methods=["GET"])
@require_user
def get_crm_stages_endpoint(client_sdr_id: int):
    stages = get_crm_stages(client_sdr_id=client_sdr_id)
    current_mapping = get_client_sync_crm(client_sdr_id).get("status_mapping")
    current_triggers = get_client_sync_crm(client_sdr_id).get("event_handlers")

    return jsonify(
        {
            "status": "success",
            "data": {
                "stages": stages,
                "mapping": current_mapping,
                "triggers": current_triggers,
            },
        }
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


@MERGE_CRM_BLUEPRINT.route("/contacts", methods=["GET"])
@require_user
def get_crm_user_contacts_from_db_endpoint(client_sdr_id: int):
    contacts = get_crm_user_contacts_from_db(client_sdr_id=client_sdr_id)
    return jsonify({"status": "success", "data": {"contacts": contacts}})

@MERGE_CRM_BLUEPRINT.route("/sync/event", methods=["PATCH"])
@require_user
def patch_event_trigger(client_sdr_id: int):
    event_mapping = (
        get_request_parameter("event_mapping", request, json=True, required=False) or {}
    )

    success = save_sellscale_crm_event_handler(
        client_sdr_id=client_sdr_id, event_handlers=event_mapping
    )
    if not success:
        return (
            jsonify({"status": "error", "message": "Failed to update event handler"}),
            400,
        )

    return jsonify({"status": "success"})


@MERGE_CRM_BLUEPRINT.route("/upload/prospect", methods=["POST"])
@require_user
def post_upload_prospect(client_sdr_id: int):
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    stage_id_override = (
        get_request_parameter("stage_id_override", request, json=True, required=False)
        or None
    )

    success, msg = upload_prospect_to_crm(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        stage_id_override=stage_id_override,
    )
    return jsonify({"success": success, "message": msg}), 200 if success else 400
