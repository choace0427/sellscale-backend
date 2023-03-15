from app import db

from flask import Blueprint, request, jsonify
from src.message_generation.services import (
    approve_message,
    research_and_generate_outreaches_for_prospect_list,
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
)
from src.message_generation.services_stack_ranked_configurations import (
    create_stack_ranked_configuration,
    edit_stack_ranked_configuration_instruction,
    edit_stack_ranked_configuration_research_point_types,
    edit_stack_ranked_configuration_name,
    delete_stack_ranked_configuration,
    get_stack_ranked_config_ordering,
    get_prompts_from_stack_ranked_config,
    toggle_stack_ranked_message_configuration_active,
)
from src.message_generation.services_few_shot_generations import (
    clear_all_good_messages_by_archetype_id,
    toggle_message_as_good_message,
    mark_messages_as_good_message,
)
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user
from model_import import OutboundCampaign
from tqdm import tqdm

MESSAGE_GENERATION_BLUEPRINT = Blueprint("message_generation", __name__)


@MESSAGE_GENERATION_BLUEPRINT.route("/batch", methods=["POST"])
def index():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )
    cta_id = get_request_parameter("cta_id", request, json=True, required=False)

    research_and_generate_outreaches_for_prospect_list(
        prospect_ids=prospect_ids, cta_id=cta_id
    )

    return "OK", 200


@MESSAGE_GENERATION_BLUEPRINT.route("/", methods=["PATCH"])
def update():
    message_id = get_request_parameter("message_id", request, json=True, required=True)
    update = get_request_parameter("update", request, json=True, required=True)

    success = update_message(message_id=message_id, update=update)
    if success:
        return "OK", 200

    return "Failed to update", 400


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
            "message_id": 36582,
        },
        ...
    ]
    """
    payload = get_request_parameter("payload", request, json=True, required=True)
    for prospect in payload:
        message_id = prospect["message_id"]
        update = prospect["completion"]
        update_message(message_id=message_id, update=update)

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

    cta = create_cta(archetype_id=archetype_id, text_value=text_value)
    return jsonify({"cta_id": cta.id})


@MESSAGE_GENERATION_BLUEPRINT.route("/delete_cta", methods=["DELETE"])
def delete_cta_request():
    from src.message_generation.services import delete_cta

    cta_id = get_request_parameter("cta_id", request, json=True, required=True)

    success = delete_cta(cta_id=cta_id)
    if success:
        return "OK", 200

    return "Failed to delete", 400


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
