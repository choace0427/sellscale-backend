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
from src.ml.services import determine_account_research_from_convo_and_bump_framework, determine_best_bump_framework_from_convo

from model_import import ProspectOverallStatus, ProspectStatus


BUMP_FRAMEWORK_BLUEPRINT = Blueprint("bump_framework", __name__)


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump", methods=["GET"])
@require_user
def get_bump_frameworks(client_sdr_id: int):
    """Gets all bump frameworks for a given client SDR and overall status"""
    overall_statuses = get_request_parameter(
        "overall_statuses", request, json=False, required=True, parameter_type=list
    ) or []
    client_archetype_ids = get_request_parameter(
        "archetype_ids", request, json=False, required=False, parameter_type=list
    ) or []
    substatuses = get_request_parameter(
        "substatuses", request, json=False, required=False, parameter_type=list
    ) or []

    overall_statuses_enumed = []
    for key, val in ProspectOverallStatus.__members__.items():
        if key in overall_statuses:
            overall_statuses_enumed.append(val)

    # Convert client_archetype_ids to list of integers
    if type(client_archetype_ids) == str:
        client_archetype_ids = [client_archetype_ids]
    client_archetype_ids = [int(ca_id) for ca_id in client_archetype_ids]

    bump_frameworks: list[dict] = get_bump_frameworks_for_sdr(
        client_sdr_id=client_sdr_id,
        overall_statuses=overall_statuses_enumed,
        substatuses=substatuses,
        client_archetype_ids=client_archetype_ids
    )

    counts = {
        "total": len(bump_frameworks),
        ProspectOverallStatus.ACCEPTED.value: 0,
        ProspectOverallStatus.BUMPED.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUESTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED.value: 0,
        ProspectStatus.ACTIVE_CONVO_OBJECTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS.value: 0,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING.value: 0,
    }
    for bump_framework in bump_frameworks:
        if bump_framework.get("overall_status") in counts:
            counts[bump_framework.get("overall_status")] += 1
        if bump_framework.get("substatus") in counts:
            counts[bump_framework.get("substatus")] += 1

    return jsonify({
        "bump_frameworks": bump_frameworks,
        "counts": counts
    }), 200


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
    length: str = get_request_parameter(
        "length", request, json=True, required=False, parameter_type=str
    ) or BumpLength.MEDIUM.value
    archetype_ids = get_request_parameter(
        "archetype_ids", request, json=True, required=False, parameter_type=list
    ) or []
    substatus = get_request_parameter(
        "substatus", request, json=True, required=False, parameter_type=str
    ) or None

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
        if key == length.upper():
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
        client_archetype_ids=archetype_ids,
        substatus=substatus,
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
    length: str = get_request_parameter(
        "length", request, json=True, required=False, parameter_type=str
    ) or BumpLength.MEDIUM.value
    archetype_ids = get_request_parameter(
        "archetype_ids", request, json=True, required=False, parameter_type=list
    ) or []

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
        if key == length.upper():
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
        length=length,
        client_archetype_ids=archetype_ids,
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


@BUMP_FRAMEWORK_BLUEPRINT.route("/autofill_research", methods=["POST"])
@require_user
def post_autofill_research_bump_framework(client_sdr_id: int):
    """Autofill account research based on a bump framework and convo history"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    convo_history = get_request_parameter(
        "convo_history", request, json=True, required=True
    )
    bump_framework_desc = get_request_parameter(
        "bump_framework_desc", request, json=True, required=True
    )
    account_research = get_request_parameter(
        "account_research", request, json=True, required=True
    )

    research_indexes = determine_account_research_from_convo_and_bump_framework(
        prospect_id, convo_history, bump_framework_desc, account_research)

    return jsonify({"message": "Determined best account research points", "data": research_indexes}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/autoselect_framework", methods=["POST"])
@require_user
def post_autoselect_bump_framework(client_sdr_id: int):
    """Autoselect bump framework based on convo history"""

    convo_history = get_request_parameter(
        "convo_history", request, json=True, required=True
    )
    bump_frameworks = get_request_parameter(
        "bump_frameworks", request, json=True, required=True
    )

    framework_index = determine_best_bump_framework_from_convo(
        convo_history, bump_frameworks)

    return jsonify({"message": "Determined index of best bump framework", "data": framework_index}), 200
