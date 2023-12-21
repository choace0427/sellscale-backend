from flask import Blueprint, request, jsonify
from src.domains.services import (
    add_email_dns_records,
    create_workmail_inbox,
    domain_blacklist_check,
    domain_setup_workflow,
    find_domain,
    find_similar_domains,
    register_aws_domain,
)
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message, URL_MAP
from app import db
import os

DOMAINS_BLUEPRINT = Blueprint("domains", __name__)


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


@DOMAINS_BLUEPRINT.route("/create_inbox", methods=["POST"])
@require_user
def post_create_workmail_inbox(client_sdr_id: int):
    domain = get_request_parameter(
        "domain", request, json=True, required=True, parameter_type=str
    )
    username = get_request_parameter(
        "username", request, json=True, required=True, parameter_type=str
    )
    password = get_request_parameter(
        "password", request, json=True, required=True, parameter_type=str
    )

    result = create_workmail_inbox(domain, username, password)

    return (
        jsonify(
            {
                "status": "success",
                "data": result,
            }
        ),
        200,
    )


@DOMAINS_BLUEPRINT.route("/setup_workflow", methods=["POST"])
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
