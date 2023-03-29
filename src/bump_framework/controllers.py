from app import db

from flask import Blueprint, request, jsonify
from model_import import BumpFramework
from src.bump_framework.services import (
    create_bump_framework,
    delete_bump_framework,
    get_bump_frameworks_for_sdr,
    toggle_bump_framework_active,
)
from src.utils.request_helpers import get_request_parameter


BUMP_FRAMEWORK_BLUEPRINT = Blueprint("bump_framework", __name__)


@BUMP_FRAMEWORK_BLUEPRINT.route("/create", methods=["POST"])
def post_create_bump_framework():
    title = get_request_parameter("title", request, json=True, required=True)
    description = get_request_parameter(
        "description", request, json=True, required=True
    )
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    overall_status = get_request_parameter(
        "overall_status", request, json=True, required=True
    )

    bump_framework = create_bump_framework(
        title=title,
        description=description,
        client_sdr_id=client_sdr_id,
        overall_status=overall_status,
    )
    if bump_framework:
        return "OK", 200
    return "Could not create bump framework.", 400


@BUMP_FRAMEWORK_BLUEPRINT.route("/", methods=["DELETE"])
def post_delete_bump_framework():
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=True
    )
    delete_bump_framework(bump_framework_id)
    return "OK", 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/", methods=["GET"])
def get_bump_frameworks():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    overall_status = get_request_parameter(
        "overall_status", request, json=True, required=True
    )
    bump_frameworks = get_bump_frameworks_for_sdr(client_sdr_id, overall_status)
    return jsonify(bump_frameworks), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/toggle_active", methods=["POST"])
def post_toggle_bump_framework_active():
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=True
    )
    toggle_bump_framework_active(bump_framework_id)
    return "OK", 200
