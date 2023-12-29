from flask import Blueprint, request, jsonify
from src.company.services import (
    authorize_slack_user,
    company_backfill,
    company_backfill_prospects,
    find_sdr_from_slack,
)
from model_import import Client
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message, URL_MAP
from app import db
import os

COMPANY_BLUEPRINT = Blueprint("company", __name__)


@COMPANY_BLUEPRINT.route("/backfill", methods=["POST"])
@require_user
def post_company_backfill(client_sdr_id: int):
    c_min = get_request_parameter(
        "min", request, json=True, required=True, parameter_type=int
    )
    c_max = get_request_parameter(
        "max", request, json=True, required=True, parameter_type=int
    )

    processed_count = company_backfill(c_min, c_max)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "processed_count": processed_count,
                },
            }
        ),
        200,
    )


@COMPANY_BLUEPRINT.route("/backfill-prospects", methods=["POST"])
@require_user
def post_company_backfill_prospects(client_sdr_id: int):
    processed_count = company_backfill_prospects(client_sdr_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "processed_count": processed_count,
                },
            }
        ),
        200,
    )


@COMPANY_BLUEPRINT.route("/sdr-from-slack-data", methods=["POST"])
@require_user
def post_company_sdr_from_slack(client_sdr_id: int):
    user_name = get_request_parameter(
        "user_name", request, json=True, required=True, parameter_type=str
    )
    user_id = get_request_parameter(
        "user_id", request, json=True, required=True, parameter_type=str
    )
    team_domain = get_request_parameter(
        "team_domain", request, json=True, required=True, parameter_type=str
    )
    team_id = get_request_parameter(
        "team_id", request, json=True, required=True, parameter_type=str
    )

    # TODO: NOTE, this gives an auth_token from a slack user_id. This is a security risk
    sdr, auth_token = find_sdr_from_slack(
        user_name=user_name, user_id=user_id, team_domain=team_domain
    )

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "sdr": sdr,
                    "auth_token": auth_token,
                },
            }
        ),
        200,
    )


@COMPANY_BLUEPRINT.route("/authorize-slack-user", methods=["POST"])
@require_user
def post_company_authorize_slack_user(client_sdr_id: int):
    slack_user_id = get_request_parameter(
        "slack_user_id", request, json=True, required=True, parameter_type=str
    )

    success = authorize_slack_user(client_sdr_id=client_sdr_id, user_id=slack_user_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": success,
            }
        ),
        200,
    )


@COMPANY_BLUEPRINT.route("/do-not-contact", methods=["POST"])
@require_user
def post_company_do_not_contact(client_sdr_id: int):
    # TODO: Add logic to add company to do not contact list

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "blacklist_company": "company_name",
                    "srd_company": "company_name",
                    "prospects_removed": 1,
                },
            }
        ),
        200,
    )
