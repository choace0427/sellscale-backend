from flask import Blueprint, request, jsonify
from src.domains.services import (
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
def get_purchase_domain(client_sdr_id: int):
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
