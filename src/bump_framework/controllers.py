from httpx import get
from app import db, app

from flask import Blueprint, request, jsonify
from model_import import BumpFramework
from src.bump_framework.models import (
    BumpFrameworkTemplates,
    BumpFrameworkToAssetMapping,
    BumpLength,
)
from src.bump_framework.services import (
    clone_bump_framework,
    create_bump_framework,
    create_bump_framework_asset_mapping,
    delete_bump_framework_asset_mapping,
    get_all_bump_framework_assets,
    get_bump_framework_count_for_sdr,
    modify_bump_framework,
    deactivate_bump_framework,
    activate_bump_framework,
    get_bump_frameworks_for_sdr,
    get_db_bump_messages,
    get_db_bump_sequence,
    send_new_framework_created_message,
)
from src.client.models import ClientArchetype, ClientSDR
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user
from src.ml.services import (
    determine_account_research_from_convo_and_bump_framework,
    determine_best_bump_framework_from_convo,
)

from src.client.services_client_archetype import get_archetype_details

from model_import import ProspectOverallStatus, ProspectStatus


BUMP_FRAMEWORK_BLUEPRINT = Blueprint("bump_framework", __name__)


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump-messages", methods=["GET"])
@require_user
def get_bump_messages(client_sdr_id: int):
    """Gets all bump messages"""
    bump_id = (
        get_request_parameter(
            "bump_id", request, json=False, required=True, parameter_type=str
        )
        or None
    )
    return get_db_bump_messages(bump_id)


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump", methods=["GET"])
@require_user
def get_bump_frameworks(client_sdr_id: int):
    """Gets all bump frameworks for a given client SDR and overall status"""
    overall_statuses = (
        get_request_parameter(
            "overall_statuses", request, json=False, required=True, parameter_type=list
        )
        or []
    )
    client_archetype_ids = (
        get_request_parameter(
            "archetype_ids", request, json=False, required=False, parameter_type=list
        )
        or []
    )
    substatuses = (
        get_request_parameter(
            "substatuses", request, json=False, required=False, parameter_type=list
        )
        or []
    )
    exclude_client_archetype_ids = (
        get_request_parameter(
            "exclude_client_archetype_ids",
            request,
            json=False,
            required=False,
            parameter_type=list,
        )
        or []
    )
    exclude_ss_default = (
        get_request_parameter(
            "exclude_ss_default",
            request,
            json=False,
            required=False,
            parameter_type=bool,
        )
        or False
    )
    unique_only = (
        get_request_parameter(
            "unique_only", request, json=False, required=False, parameter_type=bool
        )
        or False
    )
    bumped_count = (
        get_request_parameter(
            "bumped_count", request, json=False, required=False, parameter_type=int
        )
        or None
    )
    include_archetype_sequence_id = (
        get_request_parameter(
            "include_archetype_sequence_id",
            request,
            json=False,
            required=False,
            parameter_type=int,
        )
        or None
    )
    include_assets = (
        get_request_parameter(
            "include_assets", request, json=False, required=False, parameter_type=bool
        )
        or False
    )

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
        client_archetype_ids=client_archetype_ids,
        exclude_client_archetype_ids=exclude_client_archetype_ids,
        exclude_ss_default=exclude_ss_default,
        unique_only=unique_only,
        active_only=False,
        bumped_count=bumped_count,
        include_archetype_sequence_id=include_archetype_sequence_id,
        include_assets=include_assets,
    )

    counts = get_bump_framework_count_for_sdr(
        client_sdr_id=client_sdr_id,
        client_archetype_ids=client_archetype_ids,
    )

    return jsonify({"bump_frameworks": bump_frameworks, "counts": counts}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump/sellscale_default", methods=["POST"])
def post_create_bump_framework_sellscale_default():
    """Create a new bump framework"""
    description = get_request_parameter(
        "description", request, json=True, required=True, parameter_type=str
    )
    additional_instructions = (
        get_request_parameter(
            "additional_instructions",
            request,
            json=True,
            required=False,
            parameter_type=str,
        )
        or None
    )
    title = get_request_parameter(
        "title", request, json=True, required=True, parameter_type=str
    )
    overall_status = get_request_parameter(
        "overall_status", request, json=True, required=True, parameter_type=str
    )
    substatus = (
        get_request_parameter(
            "substatus", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    default = True
    use_account_research = get_request_parameter(
        "use_account_research", request, json=True, required=False, parameter_type=bool
    )
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )
    bump_framework_human_readable_prompt = get_request_parameter(
        "bump_framework_human_readable_prompt",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )

    # Get the enum value for the overall status
    found_key = False
    for key, val in ProspectOverallStatus.__members__.items():
        if key == overall_status:
            overall_status = val
            found_key = True
            break
    if not found_key:
        return jsonify({"error": "Invalid overall status."}), 400

    bump_framework_id = create_bump_framework(
        client_sdr_id=None,
        client_archetype_id=None,
        title=title,
        description=description,
        additional_instructions=additional_instructions,
        overall_status=overall_status,
        length=BumpLength.MEDIUM,
        bumped_count=0,
        bump_delay_days=2,
        substatus=substatus,
        default=default,
        use_account_research=use_account_research,
        bump_framework_human_readable_prompt=bump_framework_human_readable_prompt,
        transformer_blocklist=transformer_blocklist,
    )
    if bump_framework_id:
        return (
            jsonify(
                {
                    "message": "Successfully created bump framework",
                    "bump_framework_id": bump_framework_id,
                }
            ),
            200,
        )
    return jsonify({"error": "Could not create bump framework."}), 400


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump/sellscale_default", methods=["PATCH"])
def patch_bump_framework_sellscale_default():
    """Modifies a bump framework"""
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=True
    )
    overall_status = get_request_parameter(
        "overall_status", request, json=True, required=True, parameter_type=str
    )
    description = (
        get_request_parameter(
            "description", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    title = (
        get_request_parameter(
            "title", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    additional_instructions = (
        get_request_parameter(
            "additional_instructions",
            request,
            json=True,
            required=False,
            parameter_type=str,
        )
        or None
    )
    default = (
        get_request_parameter(
            "default", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    use_account_research = get_request_parameter(
        "use_account_research", request, json=True, required=False, parameter_type=bool
    )
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )
    inject_calendar_times = get_request_parameter(
        "inject_calendar_times", request, json=True, required=False, parameter_type=bool
    )
    bump_framework_human_readable_prompt = get_request_parameter(
        "bump_framework_human_readable_prompt",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )

    # Get the enum value for the overall status
    found_key = False
    for key, val in ProspectOverallStatus.__members__.items():
        if key == overall_status:
            overall_status = val
            found_key = True
            break

    if not found_key:
        return jsonify({"status": "error", "message": "Invalid overall status."}), 400

    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"status": "error", "message": "Bump framework not found."}), 404

    modified = modify_bump_framework(
        client_sdr_id=None,
        client_archetype_id=None,
        bump_framework_id=bump_framework_id,
        overall_status=overall_status,
        title=title,
        length=BumpLength.MEDIUM,
        description=description,
        additional_instructions=additional_instructions,
        bumped_count=0,
        bump_delay_days=2,
        use_account_research=use_account_research,
        default=default,
        blocklist=transformer_blocklist,
        additional_context=None,
        bump_framework_template_name=None,
        bump_framework_human_readable_prompt=bump_framework_human_readable_prompt,
        human_feedback=None,
        inject_calendar_times=inject_calendar_times,
    )

    return jsonify({"status": "success", "data": {}}), 200 if modified else 400


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
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    default = (
        get_request_parameter(
            "default", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    additional_instructions = (
        get_request_parameter(
            "additional_instructions",
            request,
            json=True,
            required=False,
            parameter_type=str,
        )
        or None
    )
    length: str = (
        get_request_parameter(
            "length", request, json=True, required=False, parameter_type=str
        )
        or BumpLength.MEDIUM.value
    )
    bumped_count = (
        get_request_parameter(
            "bumped_count", request, json=True, required=False, parameter_type=int
        )
        or None
    )
    bump_delay_days = (
        get_request_parameter(
            "bump_delay_days", request, json=True, required=False, parameter_type=int
        )
        or 2
    )
    substatus = (
        get_request_parameter(
            "substatus", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    use_account_research = get_request_parameter(
        "use_account_research", request, json=True, required=False, parameter_type=bool
    )
    human_readable_prompt = get_request_parameter(
        "human_readable_prompt", request, json=True, required=False, parameter_type=str
    )

    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )

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

    # If the transformer blocklist is empty, we should extend the SDR's default blocklist
    if not transformer_blocklist or len(transformer_blocklist) == 0:
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        transformer_blocklist = (
            sdr.default_transformer_blocklist
            if sdr.default_transformer_blocklist
            else []
        )

    bump_framework_id = create_bump_framework(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
        title=title,
        description=description,
        additional_instructions=additional_instructions,
        overall_status=overall_status,
        length=length,
        bumped_count=bumped_count,
        bump_delay_days=bump_delay_days,
        substatus=substatus,
        default=default,
        use_account_research=use_account_research,
        bump_framework_human_readable_prompt=human_readable_prompt,
        transformer_blocklist=transformer_blocklist,
    )
    if bump_framework_id:
        compain_name = ""
        compain_link = (
            "https://app.sellscale.com/setup/linkedin?campaign_id={compaign_id}".format(
                compaign_id=archetype_id
            )
        )
        try:
            compain_name = get_archetype_details(archetype_id).get("name", "")
        except TypeError:
            pass

        # only trigger for ACCEPTED or BUMPED overall status
        if overall_status in [
            ProspectOverallStatus.ACCEPTED,
            ProspectOverallStatus.BUMPED,
        ]:
            send_new_framework_created_message(
                client_sdr_id, title, compain_name, compain_link, archetype_id
            )

        return (
            jsonify(
                {
                    "message": "Successfully created bump framework",
                    "bump_framework_id": bump_framework_id,
                }
            ),
            200,
        )
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
    description = (
        get_request_parameter(
            "description", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    additional_instructions = (
        get_request_parameter(
            "additional_instructions",
            request,
            json=True,
            required=False,
            parameter_type=str,
        )
        or None
    )
    title = (
        get_request_parameter(
            "title", request, json=True, required=False, parameter_type=str
        )
        or None
    )
    default = (
        get_request_parameter(
            "default", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    active = (
        get_request_parameter(
            "active", request, json=True, required=False, parameter_type=bool
        )
        or False
    )
    length: str = (
        get_request_parameter(
            "length", request, json=True, required=False, parameter_type=str
        )
        or BumpLength.MEDIUM.value
    )
    bumped_count = (
        get_request_parameter(
            "bumped_count", request, json=True, required=False, parameter_type=int
        )
        or None
    )
    use_account_research = get_request_parameter(
        "use_account_research", request, json=True, required=False, parameter_type=bool
    )
    blocklist = get_request_parameter(
        "blocklist", request, json=True, required=False, parameter_type=list
    )
    bump_delay_days = (
        get_request_parameter(
            "bump_delay_days", request, json=True, required=False, parameter_type=int
        )
        or None
    )
    additional_context = get_request_parameter(
        "additional_context", request, json=True, required=False, parameter_type=str
    )
    bump_framework_template_name = get_request_parameter(
        "bump_framework_template_name",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )
    bump_framework_human_readable_prompt = get_request_parameter(
        "bump_framework_human_readable_prompt",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )
    human_feedback = get_request_parameter(
        "human_feedback", request, json=True, required=False, parameter_type=str
    )

    if bump_delay_days < 2:
        return (
            jsonify(
                {"status": "error", "message": "Bump delay must be at least 2 days."}
            ),
            400,
        )

    # Get the enum value for the overall status
    found_key = False
    for key, val in ProspectOverallStatus.__members__.items():
        if key == overall_status:
            overall_status = val
            found_key = True
            break
    if not found_key:
        return jsonify({"status": "error", "message": "Invalid overall status."}), 400

    # Get the enum value for the bump length
    found_key = False
    for key, val in BumpLength.__members__.items():
        if key == length.upper():
            length = val
            found_key = True
            break
    if not found_key:
        return jsonify({"status": "error", "message": "Invalid bump length."}), 400

    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"status": "error", "message": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "This bump framework does not belong to you.",
                }
            ),
            401,
        )

    modified = modify_bump_framework(
        client_sdr_id=client_sdr_id,
        client_archetype_id=bump_framework.client_archetype_id,
        bump_framework_id=bump_framework_id,
        overall_status=overall_status,
        title=title,
        length=length,
        description=description,
        additional_instructions=additional_instructions,
        bumped_count=bumped_count,
        bump_delay_days=bump_delay_days,
        use_account_research=use_account_research,
        default=active or default,
        active=active,
        blocklist=blocklist,
        additional_context=additional_context,
        bump_framework_template_name=bump_framework_template_name,
        bump_framework_human_readable_prompt=bump_framework_human_readable_prompt,
        human_feedback=human_feedback,
    )

    return jsonify({"status": "success", "data": {}}), 200 if modified else 400


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump/<int:bump_id>", methods=["GET"])
@require_user
def get_bump_framework(client_sdr_id: int, bump_id: int):
    """Gets a bump framework"""
    bump_framework: BumpFramework = BumpFramework.query.get(bump_id)
    if not bump_framework:
        return jsonify({"status": "error", "message": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "This bump framework does not belong to you.",
                }
            ),
            401,
        )

    return (
        jsonify(
            {"status": "success", "data": {"bump_framework": bump_framework.to_dict()}}
        ),
        200,
    )


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
        prospect_id, convo_history, bump_framework_desc, account_research
    )

    return (
        jsonify(
            {
                "message": "Determined best account research points",
                "data": research_indexes,
            }
        ),
        200,
    )


@BUMP_FRAMEWORK_BLUEPRINT.route("/autoselect_framework", methods=["POST"])
@require_user
def post_autoselect_bump_framework(client_sdr_id: int):
    """Autoselect bump framework based on convo history"""

    convo_history = get_request_parameter(
        "convo_history", request, json=True, required=True
    )
    bump_framework_ids = get_request_parameter(
        "bump_framework_ids", request, json=True, required=True
    )

    framework_index = determine_best_bump_framework_from_convo(
        convo_history, bump_framework_ids
    )

    return (
        jsonify(
            {
                "message": "Determined index of best bump framework",
                "data": framework_index,
            }
        ),
        200,
    )


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump/clone", methods=["POST"])
@require_user
def post_clone_bump_framework(client_sdr_id: int):
    """Clones a bump framework"""
    existent_bump_framework_id = get_request_parameter(
        "existent_bump_framework_id", request, json=True, required=True
    )
    new_archetype_id = get_request_parameter(
        "new_archetype_id", request, json=True, required=True
    )

    bump_framework: BumpFramework = BumpFramework.query.get(existent_bump_framework_id)
    if not bump_framework:
        return jsonify({"error": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This bump framework does not belong to you."}), 401

    archetype: ClientArchetype = ClientArchetype.query.get(new_archetype_id)
    if not archetype:
        return jsonify({"error": "Archetype not found."}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This archetype does not belong to you."}), 401

    new_id = clone_bump_framework(
        client_sdr_id=client_sdr_id,
        bump_framework_id=existent_bump_framework_id,
        target_archetype_id=new_archetype_id,
    )
    if new_id != -1:
        return (
            jsonify({"status": "success", "data": {"bump_framework_id": new_id}}),
            200,
        )
    else:
        return (
            jsonify({"status": "error", "message": "Could not import bump framework"}),
            400,
        )


from src.bump_framework.services_bump_framework_templates import (
    create_new_bump_framework_template,
    toggle_bump_framework_template_active_status,
    update_bump_framework_template,
    get_all_active_bump_framework_templates,
)


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump_framework_templates", methods=["GET"])
def get_bump_framework_templates():
    """Gets all bump framework templates for a given client SDR"""
    bump_framework_templates: list[dict] = get_all_active_bump_framework_templates()
    return jsonify({"bump_framework_templates": bump_framework_templates}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/bump_framework_templates", methods=["POST"])
def post_create_bump_framework_template():
    """Create a new bump framework template"""
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    raw_prompt = get_request_parameter(
        "raw_prompt", request, json=True, required=True, parameter_type=str
    )
    human_readable_prompt = get_request_parameter(
        "human_readable_prompt", request, json=True, required=True, parameter_type=str
    )
    length = get_request_parameter(
        "length", request, json=True, required=True, parameter_type=str
    )
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )
    tone = get_request_parameter(
        "tone", request, json=True, required=False, parameter_type=str
    )
    labels = get_request_parameter(
        "labels", request, json=True, required=False, parameter_type=list
    )

    create_new_bump_framework_template(
        name=name,
        raw_prompt=raw_prompt,
        human_readable_prompt=human_readable_prompt,
        length=length,
        transformer_blocklist=transformer_blocklist,
        tone=tone,
        labels=labels,
    )
    return jsonify({"message": "Successfully created bump framework template"}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route(
    "/bump_framework_templates/<int:bft_id>", methods=["PATCH"]
)
def patch_bump_framework_template(bft_id: int):
    """Modifies a bump framework template"""
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    raw_prompt = get_request_parameter(
        "raw_prompt", request, json=True, required=True, parameter_type=str
    )
    human_readable_prompt = get_request_parameter(
        "human_readable_prompt", request, json=True, required=True, parameter_type=str
    )
    length = get_request_parameter(
        "length", request, json=True, required=True, parameter_type=str
    )
    transformer_blocklist = get_request_parameter(
        "transformer_blocklist", request, json=True, required=False, parameter_type=list
    )
    tone = get_request_parameter(
        "tone", request, json=True, required=False, parameter_type=str
    )
    labels = get_request_parameter(
        "labels", request, json=True, required=False, parameter_type=list
    )

    update_bump_framework_template(
        bft_id=bft_id,
        name=name,
        raw_prompt=raw_prompt,
        human_readable_prompt=human_readable_prompt,
        length=length,
        transformer_blocklist=transformer_blocklist,
        tone=tone,
        labels=labels,
    )
    return jsonify({"message": "Successfully updated bump framework template"}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route(
    "/bump_framework_templates/toggle_active_status", methods=["POST"]
)
def post_toggle_bump_framework_template_active_status():
    """Toggles active status of a bump framework template"""
    bft_id = get_request_parameter(
        "bft_id", request, json=True, required=True, parameter_type=int
    )

    toggle_bump_framework_template_active_status(bft_id=bft_id)
    return (
        jsonify(
            {"message": "Successfully toggled bump framework template active status"}
        ),
        200,
    )


@BUMP_FRAMEWORK_BLUEPRINT.route("/sequence", methods=["GET"])
@require_user
def get_bump_sequence(client_sdr_id: int):
    """Get bump sequence"""
    archetype_id = (
        get_request_parameter(
            "archetype_id", request, json=False, required=True, parameter_type=str
        )
        or None
    )
    return get_db_bump_sequence(archetype_id)


@BUMP_FRAMEWORK_BLUEPRINT.route("/create_asset_mapping", methods=["POST"])
@require_user
def create_asset_mapping(client_sdr_id: int):
    """Creates an asset mapping for a given client SDR"""
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=True
    )
    asset_id = get_request_parameter("asset_id", request, json=True, required=True)

    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"error": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This bump framework does not belong to you."}), 401

    create_bump_framework_asset_mapping(
        bump_framework_id=bump_framework_id, client_assets_id=asset_id
    )

    return jsonify({"message": "Asset mapping created."}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/delete_asset_mapping", methods=["POST"])
@require_user
def delete_asset_mapping(client_sdr_id: int):
    """Deletes an asset mapping for a given client SDR"""
    bump_framework_to_asset_mapping_id = get_request_parameter(
        "bump_framework_to_asset_mapping_id", request, json=True, required=True
    )

    bump_framework_to_asset_mapping: BumpFrameworkToAssetMapping = (
        BumpFrameworkToAssetMapping.query.get(bump_framework_to_asset_mapping_id)
    )
    bump_framework_id: int = bump_framework_to_asset_mapping.bump_framework_id
    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"error": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This bump framework does not belong to you."}), 401

    delete_bump_framework_asset_mapping(
        bump_framework_to_asset_mapping_id=bump_framework_to_asset_mapping_id
    )

    return jsonify({"message": "Asset mapping deleted."}), 200


@BUMP_FRAMEWORK_BLUEPRINT.route("/get_all_asset_mapping", methods=["GET"])
@require_user
def get_all_asset_mapping(client_sdr_id: int):
    """Gets all asset mapping for a given client SDR"""
    bump_framework_id = get_request_parameter(
        "bump_framework_id", request, json=False, required=True
    )

    bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not bump_framework:
        return jsonify({"error": "Bump framework not found."}), 404
    elif bump_framework.client_sdr_id != client_sdr_id:
        return jsonify({"error": "This bump framework does not belong to you."}), 401

    mappings = get_all_bump_framework_assets(bump_framework_id=bump_framework_id)

    return jsonify({"mappings": mappings}), 200
