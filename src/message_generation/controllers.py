from calendar import c

from httpx import Client
from src.client.models import ClientSDR
from src.message_generation.models import StackRankedMessageGenerationConfiguration
from src.message_generation.services import (
    delete_prospect_bump,
    get_prospect_bump,
    scribe_sample_email_generation,
    update_stack_ranked_configuration_data,
)
from app import db

from flask import Blueprint, request, jsonify
from src.message_generation.services import (
    get_messages_queued_for_outreach,
    approve_message,
    update_linkedin_message_for_prospect_id,
    update_message,
    batch_approve_message_generations_by_heuristic,
    batch_disapprove_message_generations,
    pick_new_approved_message_for_prospect,
    create_generated_message_feedback,
    generate_cta_examples,
    batch_mark_prospect_email_approved_by_prospect_ids,
    generate_new_email_content_for_approved_email,
    clear_all_generated_message_jobs,
    batch_update_generated_message_ctas,
    get_generation_statuses,
    manually_mark_ai_approve,
    generate_li_convo_init_msg,
)
from src.message_generation.services_stack_ranked_configurations import (
    create_stack_ranked_configuration,
    edit_stack_ranked_configuration_instruction,
    generate_completion_for_prospect,
    get_stack_ranked_configuration_details,
    get_stack_ranked_configurations,
    edit_stack_ranked_configuration_research_point_types,
    edit_stack_ranked_configuration_name,
    delete_stack_ranked_configuration,
    get_stack_ranked_config_ordering,
    get_prompts_from_stack_ranked_config,
    toggle_stack_ranked_message_configuration_active,
    get_sample_prompt_from_config_details,
    update_stack_ranked_configuration_prompt_and_instruction,
    set_active_stack_ranked_configuration_tool,
)
from src.ml.fine_tuned_models import get_computed_prompt_completion
from src.message_generation.services_few_shot_generations import (
    clear_all_good_messages_by_archetype_id,
    toggle_message_as_good_message,
    mark_messages_as_good_message,
)
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user
from model_import import OutboundCampaign
from tqdm import tqdm
from datetime import datetime
from src.prospecting.services import *
from model_import import Prospect, ResearchPoints, ResearchPayload
from app import db
from src.ml.openai_wrappers import *
from model_import import PLGProductLeads

MESSAGE_GENERATION_BLUEPRINT = Blueprint("message_generation", __name__)


@MESSAGE_GENERATION_BLUEPRINT.route("/", methods=["GET"])
@require_user
def get_messages_queued_for_outreach_endpoint(client_sdr_id: int):
    """Returns all messages queued for outreach for a given client_sdr_id"""
    limit = get_request_parameter("limit", request, json=False, required=False) or 5
    offset = get_request_parameter("offset", request, json=False, required=False) or 0

    messages, total_count = get_messages_queued_for_outreach(
        client_sdr_id=client_sdr_id, limit=int(limit), offset=int(offset)
    )

    return (
        jsonify(
            {
                "message": "Success",
                "messages": messages,
                "total_count": total_count,
            }
        ),
        200,
    )


@MESSAGE_GENERATION_BLUEPRINT.route("/", methods=["PATCH"])
def update():
    message_id = get_request_parameter("message_id", request, json=True, required=True)
    update = get_request_parameter("update", request, json=True, required=True)

    success = update_message(message_id=message_id, update=update)
    if success:
        return jsonify({"message": "Successfully updated the message"}), 200

    return (
        jsonify(
            {
                "message": "Failed to update. Please try again. Contact engineer if error persists."
            }
        ),
        400,
    )


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/<message_id>/patch_message_ai_approve", methods=["PATCH"]
)
def patch_message_ai_approve_endpoint(message_id: int):
    """Manually marks GeneratedMessage.ai_approved to a value (True or False)"""
    # TODO Eventually needs auth
    new_ai_approve_status = get_request_parameter(
        "new_ai_approve_status", request, json=True, required=True, parameter_type=bool
    )
    success = manually_mark_ai_approve(
        generated_message_id=message_id, new_ai_approve_status=new_ai_approve_status
    )
    if success:
        human_readable = "approved" if new_ai_approve_status else "unapproved"
        return jsonify({"message": f"Message marked as {human_readable}"}), 200

    return jsonify({"message": "Failed to update"}), 400


@MESSAGE_GENERATION_BLUEPRINT.route("/batch_update", methods=["PATCH"])
def batch_update_messages():
    """
    payload = [
        {
            "linkedin_url": "linkedin.com/in/jameszw",
            "id": 2028,
            "full_name": "James Wang",
            "title": "VP of Sales Ops & Strategy at Velocity Global",
            "company": "Velocity Global",
            "completion": "This is a test 1\n",
            "prospect_id": 36582,
        },
        ...
    ]
    """
    payload = get_request_parameter("payload", request, json=True, required=True)
    for prospect in payload:
        prospect_id = prospect["prospect_id"]
        update = prospect["completion"]
        update_linkedin_message_for_prospect_id(prospect_id=prospect_id, update=update)

    return "OK", 200


@MESSAGE_GENERATION_BLUEPRINT.route("/approve", methods=["POST"])
def approve():
    message_id = get_request_parameter("message_id", request, json=True, required=True)

    success = approve_message(message_id=message_id)
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/batch_approve", methods=["POST"])
def post_batch_approve_message_generations_by_heuristic():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    success = batch_approve_message_generations_by_heuristic(prospect_ids=prospect_ids)
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/pick_new_approved_message", methods=["POST"])
def pick_new_approved_message():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    message_id = get_request_parameter("message_id", request, json=True, required=True)

    success = pick_new_approved_message_for_prospect(
        prospect_id=prospect_id, message_id=message_id
    )
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/batch_disapprove", methods=["POST"])
def post_batch_disapprove_message_generations_by_heuristic():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    success = batch_disapprove_message_generations(prospect_ids=prospect_ids)
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/mass_update", methods=["POST"])
def mass_update_generated_messages():
    from model_import import Prospect, GeneratedMessage

    payload = get_request_parameter("payload", request, json=True, required=True)
    ids = []
    for item in payload:
        if "Message" not in item:
            return "`Message` column not in CSV", 400

        if "Prospect ID" not in item:
            return "`Prospect ID` column not in CSV", 400

        prospect_id = item["Prospect ID"]
        update = item["Message"]

        p: Prospect = Prospect.query.get(prospect_id)
        approved_message_id: int = p.approved_outreach_message_id
        message: GeneratedMessage = GeneratedMessage.query.get(approved_message_id)
        if not message:
            continue

        message.completion = update
        db.session.add(message)
        db.session.commit()

        ids.append(message.id)

    return jsonify({"message_ids": ids})


@MESSAGE_GENERATION_BLUEPRINT.route("/create_cta", methods=["POST"])
def post_create_cta():
    from src.message_generation.services import create_cta

    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    text_value = get_request_parameter("text_value", request, json=True, required=True)

    date_str = get_request_parameter(
        "expiration_date", request, json=True, required=False
    )
    expiration_date = (
        datetime.datetime.fromisoformat(date_str[:-1]) if date_str else None
    )
    cta_type = get_request_parameter("cta_type", request, json=True, required=False)

    cta = create_cta(
        archetype_id=archetype_id,
        text_value=text_value,
        expiration_date=expiration_date,
        cta_type=cta_type,
    )
    return jsonify({"cta_id": cta.id})


@MESSAGE_GENERATION_BLUEPRINT.route("/cta", methods=["PUT"])
def put_update_cta():
    from src.message_generation.services import update_cta

    cta_id = get_request_parameter("cta_id", request, json=True, required=True)
    text_value = get_request_parameter("text_value", request, json=True, required=True)

    date_str = get_request_parameter(
        "expiration_date", request, json=True, required=False
    )
    expiration_date = (
        datetime.datetime.fromisoformat(date_str[:-1]) if date_str else None
    )

    success = update_cta(
        cta_id=cta_id, text_value=text_value, expiration_date=expiration_date
    )
    if success:
        return jsonify({"message": "Success"}), 200
    else:
        return jsonify({"message": "Failed to update"}), 400


@MESSAGE_GENERATION_BLUEPRINT.route("/cta", methods=["DELETE"])
def delete_msg_cta():
    from src.message_generation.services import delete_cta

    cta_id = get_request_parameter("cta_id", request, json=True, required=True)

    success = delete_cta(cta_id=cta_id)
    if success:
        return jsonify({"message": "Success"}), 200
    else:
        return jsonify({"message": "Failed to delete"}), 400


@MESSAGE_GENERATION_BLUEPRINT.route("/delete_cta", methods=["DELETE"])
def delete_cta_request():
    from src.message_generation.services import delete_cta

    cta_id = get_request_parameter("cta_id", request, json=True, required=True)

    success = delete_cta(cta_id=cta_id)
    if success:
        return "OK", 200

    return "Failed to delete", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/cta/active", methods=["GET"])
def get_is_active_cta():
    from src.message_generation.services import is_cta_active

    cta_id = get_request_parameter(
        "cta_id", request, json=False, required=True, parameter_type=int
    )

    return jsonify({"message": "Success", "data": is_cta_active(cta_id)}), 200


@MESSAGE_GENERATION_BLUEPRINT.route("/toggle_cta_active", methods=["POST"])
def post_toggle_cta_active():
    from src.message_generation.services import toggle_cta_active

    cta_id = get_request_parameter("cta_id", request, json=True, required=True)

    success = toggle_cta_active(cta_id=cta_id)
    if success:
        return "OK", 200

    return "Failed to toggle", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/add_feedback", methods=["POST"])
def post_create_feedback():
    message_id = get_request_parameter("message_id", request, json=True, required=True)
    feedback_value = get_request_parameter(
        "feedback_value", request, json=True, required=True
    )

    success = create_generated_message_feedback(
        message_id=message_id, feedback_value=feedback_value
    )
    if success:
        return "OK", 200
    return "Failed to write feedback", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/generate_ai_made_ctas", methods=["POST"])
def post_generate_ai_made_ctas():
    company_name = get_request_parameter(
        "company_name", request, json=True, required=True
    )
    persona = get_request_parameter("persona", request, json=True, required=True)
    with_what = get_request_parameter("with_what", request, json=True, required=True)

    ctas = generate_cta_examples(
        company_name=company_name,
        persona=persona,
        with_what=with_what,
    )
    return jsonify({"ctas": ctas})


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/post_batch_mark_prospect_email_approved", methods=["POST"]
)
def post_batch_mark_prospect_email_approved():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    success = batch_mark_prospect_email_approved_by_prospect_ids(
        prospect_ids=prospect_ids
    )
    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/pick_new_approved_email", methods=["POST"])
def pick_new_approved_email():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )

    generate_new_email_content_for_approved_email(
        prospect_id=prospect_id,
    )

    return "OK", 200


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/clear_message_generation_jobs_queue", methods=["POST"]
)
def post_clear_all_generated_message_jobs():
    success = clear_all_generated_message_jobs()
    if success:
        return "OK", 200
    return "Failed to clear all generated message jobs", 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/clear_all_good_messages_by_archetype_id", methods=["POST"]
)
def post_clear_all_good_messages_by_archetype_id():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    success = clear_all_good_messages_by_archetype_id(archetype_id=archetype_id)
    if success:
        return "OK", 200
    return "Failed to clear all good messages by archetype id", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/toggle_message_as_good_message", methods=["POST"])
def post_toggle_message_as_good_message():
    message_id = get_request_parameter("message_id", request, json=True, required=True)
    success = toggle_message_as_good_message(message_id=message_id)
    if success:
        return "OK", 200
    return "Failed to toggle message as good message", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/mark_messages_as_good_message", methods=["POST"])
def post_mark_messages_as_good_message():
    message_ids = get_request_parameter(
        "message_ids", request, json=True, required=True
    )
    success = mark_messages_as_good_message(generated_message_ids=message_ids)
    if success:
        return "OK", 200
    return "Failed to mark messages as good message", 400


@MESSAGE_GENERATION_BLUEPRINT.route("/update_ctas", methods=["POST"])
def post_update_ctas():
    payload = get_request_parameter("payload", request, json=True, required=True)
    success = batch_update_generated_message_ctas(
        payload=payload,
    )
    if success:
        return "OK", 200
    return "Failed to update ctas", 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/create_stack_ranked_configuration", methods=["POST"]
)
def post_create_stack_ranked_configuration():
    configuration_type = get_request_parameter(
        "configuration_type", request, json=True, required=True
    )
    research_point_types = get_request_parameter(
        "research_point_types", request, json=True, required=True
    )
    instruction = get_request_parameter(
        "instruction", request, json=True, required=True
    )
    name = get_request_parameter("name", request, json=True, required=False)
    client_id = get_request_parameter("client_id", request, json=True, required=False)
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=False
    )
    generated_message_type = get_request_parameter(
        "generated_message_type", request, json=True, required=False
    )

    success, message = create_stack_ranked_configuration(
        configuration_type=configuration_type,
        research_point_types=research_point_types,
        instruction=instruction,
        name=name,
        client_id=client_id,
        archetype_id=archetype_id,
        generated_message_type=generated_message_type,
    )
    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/edit_stack_ranked_configuration/instruction", methods=["POST"]
)
def post_edit_stack_ranked_configuration_instruction():
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    instruction = get_request_parameter(
        "instruction", request, json=True, required=True
    )

    success, message = edit_stack_ranked_configuration_instruction(
        stack_ranked_configuration_id=configuration_id,
        instruction=instruction,
    )
    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/edit_stack_ranked_configuration/research_point_types", methods=["POST"]
)
def post_edit_stack_ranked_configuration_research_point_types():
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    research_point_types = get_request_parameter(
        "research_point_types", request, json=True, required=True
    )

    success, message = edit_stack_ranked_configuration_research_point_types(
        stack_ranked_configuration_id=configuration_id,
        research_point_types=research_point_types,
    )
    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/edit_stack_ranked_configuration/name", methods=["POST"]
)
def post_edit_stack_ranked_configuration_name():
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    name = get_request_parameter("name", request, json=True, required=True)

    success, message = edit_stack_ranked_configuration_name(
        stack_ranked_configuration_id=configuration_id,
        name=name,
    )
    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route("/stack_ranked_configuration", methods=["DELETE"])
def delete_stack_ranked_configuration_endpoint():
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )

    success, message = delete_stack_ranked_configuration(
        stack_ranked_configuration_id=configuration_id,
    )
    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_priority", methods=["GET"]
)
def get_stack_ranked_configuration_priority_endpoint():
    generated_message_type = get_request_parameter(
        "generated_message_type", request, json=False, required=True
    )
    client_id = get_request_parameter("client_id", request, json=False, required=False)
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=False
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=False
    )

    ordered_configuration_lists = get_stack_ranked_config_ordering(
        generated_message_type=generated_message_type,
        archetype_id=archetype_id,
        client_id=client_id,
        prospect_id=prospect_id,
    )
    return (
        jsonify(
            [
                [config.to_dict() for config in config_list]
                for config_list in ordered_configuration_lists
            ]
        ),
        200,
    )


@MESSAGE_GENERATION_BLUEPRINT.route("/stack_ranked_configurations", methods=["GET"])
@require_user
def get_all_stack_ranked_configurations(client_sdr_id: int):
    """Get all stack ranked configurations for a given client_sdr_id"""
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=False
    )

    configs = get_stack_ranked_configurations(client_sdr_id, archetype_id=archetype_id)

    return jsonify({"message": "Success", "data": [c.to_dict() for c in configs]}), 200


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configurations/<int:config_id>", methods=["GET"]
)
@require_user
def post_stack_ranked_configuration_tool(client_sdr_id: int, config_id: int):
    """Get all stack ranked configurations for a given client_sdr_id"""

    config, message = get_stack_ranked_configuration_details(
        client_sdr_id=client_sdr_id, config_id=config_id
    )

    if not config:
        return jsonify({"message": message}), 400

    return jsonify({"message": "Success", "data": config}), 200


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration/generate_completion_for_prospect", methods=["POST"]
)
@require_user
def post_stack_ranked_configuration_tool_generate_completion_for_prospect(
    client_sdr_id: int,
):
    """Get all stack ranked configurations for a given client_sdr_id"""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    computed_prompt = get_request_parameter(
        "computed_prompt", request, json=True, required=True
    )

    message, error_message = generate_completion_for_prospect(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        computed_prompt=computed_prompt,
    )

    if not message:
        return jsonify({"message": error_message}), 400

    return jsonify({"message": "Success", "completion": message}), 200


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/get_prompts", methods=["POST"]
)
def get_stack_ranked_configuration_tool_prompts():
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    list_of_research_points = get_request_parameter(
        "list_of_research_points", request, json=True, required=True
    )

    return jsonify(
        get_prompts_from_stack_ranked_config(
            configuration_id=configuration_id,
            prospect_id=prospect_id,
            list_of_research_points=list_of_research_points,
        )
    )


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/generate_sample", methods=["POST"]
)
def generate_stack_ranked_configuration_tool_sample():
    """
    Generates a sample message for a stack ranked configuration
    """
    computed_prompt = get_request_parameter(
        "computed_prompt", request, json=True, required=True
    )
    prompt = get_request_parameter("prompt", request, json=True, required=True)
    response, prompt = get_computed_prompt_completion(
        computed_prompt=computed_prompt, prompt=prompt
    )

    return jsonify({"response": response, "full_prompt": prompt})


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/set_active", methods=["POST"]
)
def set_active_stack_ranked_configuration_tool_endpoint():
    """
    Sets whether the stack ranked configuration is active or not
    """
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    set_active = get_request_parameter(
        "set_active", request, json=True, required=True, parameter_type=bool
    )

    success, msg = set_active_stack_ranked_configuration_tool(
        configuration_id=configuration_id, set_active=set_active
    )

    if success:
        return jsonify({"message": "Successfully updated configuration_tool"}), 200
    else:
        return (
            jsonify(
                {
                    "message": "Failed to update. Please try again. Contact engineer if error persists."
                }
            ),
            400,
        )


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/generate_sample_prompt", methods=["POST"]
)
def generate_stack_ranked_configuration_tool_sample_prompt():
    """
    Generates a sample message for a stack ranked configuration
    """
    generated_message_type = get_request_parameter(
        "generated_message_type", request, json=True, required=True
    )
    research_point_types = get_request_parameter(
        "research_point_types", request, json=True, required=True
    )
    configuration_type = get_request_parameter(
        "configuration_type", request, json=True, required=True
    )
    client_id = get_request_parameter("client_id", request, json=True, required=False)

    (
        prompt,
        selected_research_point_types,
        _,
        _,
        _,
        _,
    ) = get_sample_prompt_from_config_details(
        generated_message_type=generated_message_type,
        research_point_types=research_point_types,
        configuration_type=configuration_type,
        client_id=client_id,
    )
    return jsonify(
        {
            "prompt": prompt,
            "selected_research_point_types": selected_research_point_types,
        }
    )


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/toggle_active", methods=["POST"]
)
def post_toggle_stack_ranked_configuration_tool_active():
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    success, message = toggle_stack_ranked_message_configuration_active(
        stack_ranked_configuration_id=configuration_id
    )

    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/get_generation_status/<campaign_id>", methods=["GET"]
)
@require_user
def get_generation_status_endpoint(client_sdr_id: int, campaign_id: int):
    """Gets the message generation status for a campaign

    Requires authentication
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign.client_sdr_id != client_sdr_id:
        return (
            jsonify({"error": "This user is unauthorized to view this campaign"}),
            401,
        )

    generation_statuses = get_generation_statuses(campaign_id)

    return jsonify({"generation_statuses": generation_statuses}), 200


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/update_instruction_and_prompt", methods=["POST"]
)
def post_update_stack_ranked_configuration_tool_instruction_and_prompt():
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    new_prompt = get_request_parameter("new_prompt", request, json=True, required=True)

    success, message = update_stack_ranked_configuration_prompt_and_instruction(
        configuration_id=configuration_id,
        new_prompt=new_prompt,
    )
    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/update_stack_ranked_configuration_data",
    methods=["POST"],
)
@require_user
def post_update_stack_ranked_configuration_data(client_sdr_id: int):
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    srmgc = StackRankedMessageGenerationConfiguration.query.get(configuration_id)
    if not srmgc or srmgc.client_id != client_sdr.client_id:
        return "Unauthorized", 401

    instruction = get_request_parameter(
        "instruction", request, json=True, required=False
    )
    completion_1 = get_request_parameter(
        "completion_1", request, json=True, required=False
    )
    completion_2 = get_request_parameter(
        "completion_2", request, json=True, required=False
    )
    completion_3 = get_request_parameter(
        "completion_3", request, json=True, required=False
    )
    completion_4 = get_request_parameter(
        "completion_4", request, json=True, required=False
    )
    completion_5 = get_request_parameter(
        "completion_5", request, json=True, required=False
    )
    completion_6 = get_request_parameter(
        "completion_6", request, json=True, required=False
    )
    completion_7 = get_request_parameter(
        "completion_7", request, json=True, required=False
    )

    success = update_stack_ranked_configuration_data(
        configuration_id=configuration_id,
        instruction=instruction,
        completion_1=completion_1,
        completion_2=completion_2,
        completion_3=completion_3,
        completion_4=completion_4,
        completion_5=completion_5,
        completion_6=completion_6,
        completion_7=completion_7,
    )

    if success:
        return "OK", 200

    return "Failed to update", 400


@MESSAGE_GENERATION_BLUEPRINT.route(
    "/stack_ranked_configuration_tool/update_computed_prompt", methods=["POST"]
)
@require_user
def post_update_stack_ranked_configuration_tool_instruction_and_prompt_secure(
    client_sdr_id: int,
):
    configuration_id = get_request_parameter(
        "configuration_id", request, json=True, required=True
    )
    new_prompt = get_request_parameter("new_prompt", request, json=True, required=True)

    success, message = update_stack_ranked_configuration_prompt_and_instruction(
        configuration_id=configuration_id,
        new_prompt=new_prompt,
        client_sdr_id=client_sdr_id,
    )
    if success:
        return "OK", 200
    return message, 400


@MESSAGE_GENERATION_BLUEPRINT.route("/auto_bump", methods=["GET"])
@require_user
def get_auto_bump_message(client_sdr_id: int):
    """
    Get an auto bump message
    """
    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True
    )

    result = get_prospect_bump(
        client_sdr_id=client_sdr_id,
        prospect_id=int(prospect_id),
    )
    if not result:
        return jsonify({"message": "Failed to fetch"}), 400

    return jsonify({"message": "Success", "data": result.to_dict()}), 200


@MESSAGE_GENERATION_BLUEPRINT.route("/auto_bump", methods=["DELETE"])
@require_user
def delete_auto_bump_message(client_sdr_id: int):
    """
    Deletes an auto bump message
    """
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )

    success = delete_prospect_bump(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
    )
    if not success:
        return jsonify({"message": "Failed to delete"}), 400

    return jsonify({"message": "Success"}), 200


@MESSAGE_GENERATION_BLUEPRINT.route("/generate_init_li_message", methods=["POST"])
@require_user
def post_generate_init_li_message(client_sdr_id: int):
    """Generates the init li outbound message for a prospect"""
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    message, meta_data = generate_li_convo_init_msg(prospect_id)

    return (
        jsonify(
            {"message": "Success", "data": {"message": message, "metadata": meta_data}}
        ),
        200,
    )


@MESSAGE_GENERATION_BLUEPRINT.route("/generate_scribe_completion", methods=["POST"])
def post_generate_scribe_completion():
    USER_LINKEDIN = get_request_parameter(
        "user_linkedin", request, json=True, required=True
    )
    USER_EMAIL = get_request_parameter("user_email", request, json=True, required=True)
    PROSPECT_LINKEDIN = get_request_parameter(
        "prospect_linkedin", request, json=True, required=True
    )
    BLOCK_KEY = get_request_parameter("block_key", request, json=True, required=True)

    plg_product_lead_exists = PLGProductLeads.query.filter_by(email=USER_EMAIL).first()
    if plg_product_lead_exists:
        send_slack_message(
            message=f"[{USER_EMAIL}] Existing PLG lead created a new Scribe Completion Job! From {USER_LINKEDIN} to {PROSPECT_LINKEDIN}",
            webhook_urls=[URL_MAP["sales-leads-plg-demo"]],
        )
    else:
        send_slack_message(
            message=f"🎉✅🎉✅ New Sales Lead from PLG Website Demo!\nEmail: {USER_EMAIL}\nThey are sending an email from {USER_LINKEDIN} → {PROSPECT_LINKEDIN}\nThis was the block key:\n---\n{BLOCK_KEY}\n---",
            webhook_urls=[URL_MAP["sales-leads-plg-demo"]],
        )

    send_slack_message(
        message=f"[{USER_EMAIL}] 🎉🪄 New Scribe Completion Job Triggered! From {USER_LINKEDIN} to {PROSPECT_LINKEDIN}",
        webhook_urls=[URL_MAP["ops-scribe-submissions"]],
    )

    plg_product_leads_in_last_hour = PLGProductLeads.query.filter(
        PLGProductLeads.created_at
        > datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    ).count()
    if plg_product_leads_in_last_hour > 1000:
        return "Too many submissions in the last hour", 400

    scribe_sample_email_generation.apply_async(
        args=[USER_LINKEDIN, USER_EMAIL, PROSPECT_LINKEDIN, BLOCK_KEY],
        priority=1,
    )

    return "OK", 200
