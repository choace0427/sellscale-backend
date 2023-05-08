from app import db, app

from flask import Blueprint, request, jsonify
from model_import import BumpFramework
from src.bump_framework.models import BumpLength
from src.bump_framework.services import (
    create_bump_framework,
    modify_bump_framework,
    deactivate_bump_framework,
    activate_bump_framework,
    get_bump_frameworks_for_sdr,
)
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user

from model_import import ProspectOverallStatus


BUMP_FRAMEWORK_BLUEPRINT = Blueprint("bump_framework", __name__)


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump", methods=["GET"])
@require_user
def get_bump_frameworks(client_sdr_id: int):
    """Gets all bump frameworks for a given client SDR and overall status"""
    overall_status = get_request_parameter(
        "overall_status", request, json=False, required=True
    )

    found_key = False
    for key, val in ProspectOverallStatus.__members__.items():
        if key == overall_status:
            overall_status = val
            found_key = True
            break
    if not found_key:
        return jsonify({"error": "Invalid overall status."}), 400

    bump_frameworks = get_bump_frameworks_for_sdr(client_sdr_id, overall_status)
    return jsonify({"bump_frameworks": bump_frameworks}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump", methods=["POST"])
@require_user
def post_create_bump_framework(client_sdr_id: int):
    """Create a new bump framework"""
    description = get_request_parameter(
        "description", request, json=True, required=True, parameter_type=str
    )
    title = get_request_parameter(
        "title", request, json=True, required=True, parameter_type=str
    )
    overall_status = get_request_parameter(
        "overall_status", request, json=True, required=True, parameter_type=str
    )
    default = get_request_parameter(
        "default", request, json=True, required=False, parameter_type=bool
    ) or False
    length = get_request_parameter(
        "length", request, json=True, required=True, parameter_type=str
    ) or BumpLength.MEDIUM

    # Get the enum value for the overall status
    found_key = False
    for key, val in ProspectOverallStatus.__members__.items():
        if key == overall_status:
            overall_status = val
            found_key = True
            break
    if not found_key:
        return jsonify({"error": "Invalid overall status."}), 400

    # Get the enum value for the bump length
    found_key = False
    for key, val in BumpLength.__members__.items():
        if key == length:
            length = val
            found_key = True
            break
    if not found_key:
        return jsonify({"error": "Invalid bump length."}), 400

    bump_framework_id = create_bump_framework(
        title=title,
        description=description,
        overall_status=overall_status,
        length=length,
        client_sdr_id=client_sdr_id,
        default=default,
    )
    if bump_framework_id:
        return jsonify({"message": "Successfully created bump framework", "bump_framework_id": bump_framework_id}), 200
    return jsonify({"error": "Could not create bump framework."}), 400


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump", methods=["PATCH"])
@require_user
def patch_bump_framework(client_sdr_id: int):
    """Modifies a bump framework"""
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=True
    )
    overall_status = get_request_parameter(
        "overall_status", request, json=True, required=True, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, parameter_type=str
    ) or None
    title = get_request_parameter(
        "title", request, json=True, required=False, parameter_type=str
    ) or None
    default = get_request_parameter(
        "default", request, json=True, required=False, parameter_type=bool
    ) or False
    length = get_request_parameter(
        "length", request, json=True, required=True, parameter_type=str
    ) or BumpLength.MEDIUM

    # Get the enum value for the overall status
    found_key = False
    for key, val in ProspectOverallStatus.__members__.items():
        if key == overall_status:
            overall_status = val
            found_key = True
            break
    if not found_key:
        return jsonify({"error": "Invalid overall status."}), 400

    # Get the enum value for the bump length
    found_key = False
    for key, val in BumpLength.__members__.items():
        if key == length:
            length = val
            found_key = True
            break
    if not found_key:
        return jsonify({"error": "Invalid bump length."}), 400

    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"error": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This bump framework does not belong to you."}), 401

    modified = modify_bump_framework(
        client_sdr_id=client_sdr_id,
        bump_framework_id=bump_framework_id,
        overall_status=overall_status,
        title=title,
        description=description,
        default=default,
    )

    return jsonify({"message": "Bump framework updated."}), 200 if modified else 400


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump/deactivate", methods=["POST"])
@require_user
def post_deactivate_bump_framework(client_sdr_id: int):
    """Deletes a bump framework"""
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=True
    )

    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"error": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This bump framework does not belong to you."}), 401

    deactivate_bump_framework(client_sdr_id, bump_framework_id)
    return jsonify({"message": "Bump framework deactivated."}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump/activate", methods=["POST"])
@require_user
def post_activate_bump_framework(client_sdr_id: int):
    """Activates a bump framework"""
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=True
    )

    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"error": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This bump framework does not belong to you."}), 401

    activate_bump_framework(client_sdr_id, bump_framework_id)
    return jsonify({"message": "Bump framework activated."}), 200
