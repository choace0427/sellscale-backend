from flask import Blueprint, request, jsonify
from src.domains.services import (
    add_email_dns_records,
    create_domain_entry,
    create_workmail_inbox,
    domain_blacklist_check,
    domain_purchase_workflow,
    domain_setup_workflow,
    find_domain,
    find_similar_domains,
    patch_domain_entry,
    register_aws_domain,
    validate_domain_configuration,
    workmail_setup_workflow,
)
from model_import import ClientSDR, Client
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message, URL_MAP
from app import db
import os

DOMAINS_BLUEPRINT = Blueprint("domains", __name__)


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


@DOMAINS_BLUEPRINT.route("/purchase", methods=["POST"])
@require_user
def post_purchase_domain(client_sdr_id: int):
    domain = get_request_parameter(
        "domain", request, json=True, required=True, parameter_type=str
    )

    result = register_aws_domain(domain)

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/add_dns_records", methods=["POST"])
@require_user
def post_add_dns_records(client_sdr_id: int):
    domain = get_request_parameter(
        "domain", request, json=True, required=True, parameter_type=str
    )

    result = add_email_dns_records(domain)

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

    result = domain_purchase_workflow(client_id=client_id, domain_name=domain)

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
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
