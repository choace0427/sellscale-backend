from flask import Blueprint, jsonify, request
from src.client.models import ClientArchetype

from model_import import ClientSDR
from src.utils.request_helpers import get_request_parameter
from src.authentication.decorators import require_user

from src.voice_builder.services import (
    conduct_research_for_n_prospects,
    create_voice_builder_onboarding,
    create_voice_builder_samples,
    delete_voice_builder_sample,
    get_voice_builder_samples,
    generate_computed_prompt,
    update_voice_builder_onboarding_instruction,
    edit_voice_builder_sample,
    delete_voice_builder_sample,
    convert_voice_builder_onboarding_to_stack_ranked_message_config,
)
from model_import import VoiceBuilderOnboarding

VOICE_BUILDER_BLUEPRINT = Blueprint("voice_builder", __name__)


@VOICE_BUILDER_BLUEPRINT.route("/generate_research", methods=["POST"])
def get_account_research_points():
    client_id = get_request_parameter("client_id", request, json=True, required=True)
    n = get_request_parameter("n", request, json=True, required=True)

    success = conduct_research_for_n_prospects(client_id=client_id, n=n)
    if success:
        return "Success", 200
    return "Failed to generate research.", 400


@VOICE_BUILDER_BLUEPRINT.route("/create_onboarding", methods=["POST"])
def create_onboarding():
    client_id = get_request_parameter(
        "client_id", request, json=True, required=False, parameter_type=int
    )
    generated_message_type = get_request_parameter(
        "generated_message_type", request, json=True, required=True
    )
    instruction = get_request_parameter(
        "instruction", request, json=True, required=True
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=False, parameter_type=int
    )

    if client_archetype_id and not client_id:
        archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
        if not archetype:
            return "Failed to find client archetype.", 400
        client_id = archetype.client_id

    onboarding: VoiceBuilderOnboarding = create_voice_builder_onboarding(
        client_id=client_id,
        generated_message_type=generated_message_type,
        instruction=instruction,
        client_archetype_id=client_archetype_id,
    )
    if onboarding:
        return jsonify(onboarding.to_dict()), 200
    return "Failed to create voice builder onboarding.", 400


@VOICE_BUILDER_BLUEPRINT.route("/create_samples", methods=["POST"])
def create_samples():
    voice_builder_onboarding_id: int = get_request_parameter(
        "voice_builder_onboarding_id", request, json=True, required=True
    )
    n: int = get_request_parameter("n", request, json=True, required=True)
    samples = create_voice_builder_samples(
        voice_builder_onboarding_id=voice_builder_onboarding_id, n=n
    )
    return jsonify({"message": "Success", "data": samples}), 200


@VOICE_BUILDER_BLUEPRINT.route("/get_details", methods=["GET"])
def get_details():
    voice_builder_onboarding_id: int = get_request_parameter(
        "voice_builder_onboarding_id", request, json=False, required=False
    ) or get_request_parameter(
        "voice_builder_onboarding_id", request, json=True, required=False
    )
    voice_builder_onboarding = VoiceBuilderOnboarding.query.get(
        voice_builder_onboarding_id
    )
    if not voice_builder_onboarding:
        return "Voice builder onboarding not found.", 400

    voice_builder_onboarding_info = voice_builder_onboarding.to_dict()
    sample_info = get_voice_builder_samples(
        voice_builder_onboarding_id=voice_builder_onboarding_id
    )
    computed_prompt = generate_computed_prompt(
        voice_builder_onboarding_id=voice_builder_onboarding_id
    )

    return (
        jsonify(
            {
                "voice_builder_onboarding_info": voice_builder_onboarding_info,
                "sample_info": sample_info,
                "computed_prompt": computed_prompt,
            }
        ),
        200,
    )


@VOICE_BUILDER_BLUEPRINT.route("/onboardings", methods=["GET"])
@require_user
def get_onboardings_endpoint(client_sdr_id: int):
    
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    
    onboardings: list[VoiceBuilderOnboarding] = VoiceBuilderOnboarding.query.filter_by(
        client_archetype_id=client_archetype_id,
    ).all()

    return jsonify({"message": "Success", "data": 
      [onboarding.to_dict() for onboarding in onboardings]
    }), 200


@VOICE_BUILDER_BLUEPRINT.route("/update_instruction", methods=["POST"])
def update_voice_builder_instruction():
    voice_builder_onboarding_id: int = get_request_parameter(
        "voice_builder_onboarding_id", request, json=True, required=True
    )
    instruction = get_request_parameter(
        "instruction", request, json=True, required=True
    )
    success = update_voice_builder_onboarding_instruction(
        voice_builder_onboarding_id=voice_builder_onboarding_id,
        updated_instruction=instruction,
    )
    if success:
        return "Success", 200
    return "Failed to update voice builder instruction.", 400


@VOICE_BUILDER_BLUEPRINT.route("/edit_sample", methods=["POST"])
def post_edit_voice_builder_sample():
    voice_builder_sample_id: int = get_request_parameter(
        "voice_builder_sample_id", request, json=True, required=True
    )
    updated_text = get_request_parameter(
        "updated_text", request, json=True, required=True
    )
    success = edit_voice_builder_sample(
        voice_builder_sample_id=voice_builder_sample_id, updated_completion=updated_text
    )
    if success:
        return "Success", 200
    return "Failed to edit voice builder sample.", 400


@VOICE_BUILDER_BLUEPRINT.route("/delete_sample", methods=["POST"])
def post_delete_voice_builder_sample():
    voice_builder_sample_id: int = get_request_parameter(
        "voice_builder_sample_id", request, json=True, required=True
    )
    success = delete_voice_builder_sample(
        voice_builder_sample_id=voice_builder_sample_id
    )
    if success:
        return "Success", 200
    return "Failed to delete voice builder sample.", 400


@VOICE_BUILDER_BLUEPRINT.route("/convert_to_pattern", methods=["POST"])
def post_convert_to_pattern():
    voice_builder_onboarding_id: int = get_request_parameter(
        "voice_builder_onboarding_id", request, json=True, required=True
    )
    srmc_dict = convert_voice_builder_onboarding_to_stack_ranked_message_config(
        voice_builder_onboarding_id=voice_builder_onboarding_id
    )
    if srmc_dict:
        return jsonify(srmc_dict), 200
    return "Failed to convert voice builder onboarding to pattern.", 400
