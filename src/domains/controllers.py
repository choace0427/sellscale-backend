from flask import Blueprint, request, jsonify
from src.client.sdr.email.services_email_bank import get_sdr_email_banks_for_client
from src.domains.services import (
    create_domain_entry,
    create_multiple_domain_and_managed_inboxes,
    delete_domain,
    domain_blacklist_check,
    domain_purchase_workflow,
    domain_setup_workflow,
    find_domain,
    find_similar_domains,
    get_domain_details,
    patch_domain_entry,
    request_domain_inboxes,
    validate_domain_configuration,
    workmail_setup_workflow, toggle_domain,
)
from model_import import ClientSDR, Client
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter

DOMAINS_BLUEPRINT = Blueprint("domains", __name__)


@DOMAINS_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_all_domain_details(client_sdr_id):
    """Gets all domain details for a client"""
    include_client_email_banks = get_request_parameter(
        "include_client_email_banks",
        request,
        json=False,
        required=False,
        parameter_type=bool,
    )
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client: Client = Client.query.filter_by(id=client_sdr.client_id).first()

    domain_details = get_domain_details(
        client_id=client.id, include_client_email_banks=include_client_email_banks
    )
    sdr_inbox_details = get_sdr_email_banks_for_client(client_id=client.id)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "domain_details": domain_details,
                    "sdr_inbox_details": sdr_inbox_details,
                },
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/toggle_domain", methods=["POST"])
@require_user
def post_toggle_domain(client_sdr_id: int):
    domain_id = get_request_parameter(
        "domain_id", request, json=True, required=True, parameter_type=int
    )
    toggle_on = get_request_parameter(
        "toggle_on", request, json=True, required=True, parameter_type=bool
    )

    success = toggle_domain(domain_id=domain_id, client_sdr_id=client_sdr_id, toggle_on=toggle_on)

    if success:
        return (
            jsonify(
                {
                    "status": "success",
                }
            ),
            200,
        )
    else:
        return (
            jsonify(
                {
                    "status": "error",
                }
            ),
            400,
        )


@DOMAINS_BLUEPRINT.route("/", methods=["POST"])
@require_user
def post_domain():
    domain = get_request_parameter(
        "domain", request, json=True, required=True, parameter_type=str
    )
    forward_to = get_request_parameter(
        "forward_to", request, json=True, required=True, parameter_type=str
    )
    dmarc_record = get_request_parameter(
        "dmarc_record", request, json=True, required=False, parameter_type=str
    )
    spf_record = get_request_parameter(
        "spf_record", request, json=True, required=False, parameter_type=str
    )
    dkim_record = get_request_parameter(
        "dkim_record", request, json=True, required=False, parameter_type=str
    )

    _ = create_domain_entry(
        domain=domain,
        forward_to=forward_to,
        aws=False,
        dmarc_record=dmarc_record,
        spf_record=spf_record,
        dkim_record=dkim_record,
    )

    return (
        jsonify(
            {
                "status": "success",
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/", methods=["PATCH"])
@require_user
def patch_domain():
    domain_id = get_request_parameter(
        "domain_id", request, json=True, required=True, parameter_type=int
    )
    forward_to = get_request_parameter(
        "forward_to", request, json=True, required=True, parameter_type=str
    )

    success = patch_domain_entry(
        domain_id=domain_id,
        forward_to=forward_to,
    )

    if success:
        return (
            jsonify(
                {
                    "status": "success",
                }
            ),
            200,
        )
    else:
        return (
            jsonify(
                {
                    "status": "error",
                }
            ),
            400,
        )


@DOMAINS_BLUEPRINT.route("/<int:domain_id>", methods=["DELETE"])
@require_user
def delete_domain_endpoint(client_sdr_id: int, domain_id: int):
    """Deletes a domain"""
    success, msg = delete_domain(domain_id=domain_id)
    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": msg,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "status": "success",
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/validate", methods=["POST"])
@require_user
def post_validate_domain(client_sdr_id: int):
    domain_id = get_request_parameter(
        "domain_id", request, json=True, required=True, parameter_type=int
    )

    success = validate_domain_configuration(domain_id=domain_id)

    if success:
        return (
            jsonify(
                {
                    "status": "success",
                }
            ),
            200,
        )
    else:
        return (
            jsonify(
                {
                    "status": "error",
                }
            ),
            400,
        )


@DOMAINS_BLUEPRINT.route("/find", methods=["GET"])
@require_user
def get_find_domain(client_sdr_id: int):
    domain = get_request_parameter(
        "domain", request, json=False, required=True, parameter_type=str
    )

    result = find_domain(domain)

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("inboxes/request", methods=["POST"])
@require_user
def post_request_domain_inboxes(client_sdr_id: int):
    number_inboxes = get_request_parameter(
        "number_inboxes", request, json=True, required=True, parameter_type=int
    )

    result = request_domain_inboxes(
        client_sdr_id=client_sdr_id, number_inboxes=number_inboxes
    )
    if not result:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to request inboxes",
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "status": "success",
                "message": "Inboxes requested successfully",
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/find-similar", methods=["GET"])
@require_user
def get_find_similar_domains(client_sdr_id: int):
    domain = get_request_parameter(
        "domain", request, json=False, required=True, parameter_type=str
    )

    parts = domain.split(".")
    result = find_similar_domains(parts[0], parts[-1])

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/workflow/purchase", methods=["POST"])
@require_user
def post_purchase_workflow(client_sdr_id: int):
    domain = get_request_parameter(
        "domain", request, json=True, required=True, parameter_type=str
    )
    client_id = get_request_parameter(
        "client_id", request, json=True, required=True, parameter_type=int
    )

    success, message, id = domain_purchase_workflow(
        client_id=client_id, domain_name=domain
    )
    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": message,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "id": id,
                    "message": "Domain purchased successfully",
                },
            }
        ),
        200,
    )


# THIS ENDPOINT NEEDS TO HAVE FURTHER RESTRICTIONS
# Since we are making it available to the user, we need to have an "Admin" mode which will bypass the
# inbox limit restrictions.
@DOMAINS_BLUEPRINT.route("/workflow/domain_and_inbox", methods=["POST"])
@require_user
def post_domain_and_inbox_workflow(client_sdr_id: int):
    number_inboxes = get_request_parameter(
        "number_inboxes", request, json=True, required=True, parameter_type=int
    )

    success, message = create_multiple_domain_and_managed_inboxes(
        client_sdr_id=client_sdr_id, number_inboxes=number_inboxes
    )
    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": message,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "status": "success",
                "message": message,
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/workflow/setup", methods=["POST"])
@require_user
def post_setup_workflow(client_sdr_id: int):
    domain = get_request_parameter(
        "domain", request, json=True, required=True, parameter_type=str
    )
    username = get_request_parameter(
        "username", request, json=True, required=True, parameter_type=str
    )
    password = get_request_parameter(
        "password", request, json=True, required=True, parameter_type=str
    )

    result = domain_setup_workflow(domain, username, password)

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/workflow/workmail", methods=["POST"])
@require_user
def post_workmail_workflow(client_sdr_id: int):
    domain_id = get_request_parameter(
        "domain_id", request, json=True, required=True, parameter_type=int
    )
    username = get_request_parameter(
        "username", request, json=True, required=True, parameter_type=str
    )

    success, message = workmail_setup_workflow(
        client_sdr_id=client_sdr_id, domain_id=domain_id, username=username
    )
    if not success:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": message,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "status": "success",
                "message": message,
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/blacklist", methods=["GET"])
def get_domain_blacklist_check():
    domain = get_request_parameter(
        "domain", request, json=False, required=True, parameter_type=str
    )

    result = domain_blacklist_check(domain)

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
            }
        ),
        200,
    )
