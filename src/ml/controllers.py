from src.authentication.decorators import require_user
from app import db

from flask import Blueprint, jsonify, request
from src.ml.fine_tuned_models import get_latest_custom_model
from src.ml.models import GNLPModelType
from model_import import ClientArchetype
from src.ml.services import (
    check_statuses_of_fine_tune_jobs,
    get_fine_tune_timeline,
    initiate_fine_tune_job,
    get_aree_fix_basic,
    get_sequence_draft,
    get_sequence_value_props,
    get_icp_classification_prompt_by_archetype_id,
    post_icp_classification_prompt_change_request,
    patch_icp_classification_prompt,
    trigger_icp_classification
)
from src.ml.fine_tuned_models import get_config_completion

from src.message_generation.models import GeneratedMessage
from src.utils.request_helpers import get_request_parameter

ML_BLUEPRINT = Blueprint("ml", __name__)


@ML_BLUEPRINT.route("/fine_tune_openai_outreach_model", methods=["POST"])
def index():
    message_ids = get_request_parameter(
        "message_ids", request, json=True, required=True
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    model_type = get_request_parameter("model_type", request, json=True, required=True)

    status, message = initiate_fine_tune_job(
        archetype_id=archetype_id,
        message_ids=message_ids,
        model_type=model_type,
    )

    if status:
        return message, 200
    return message, 400


@ML_BLUEPRINT.route("/update_fine_tune_job_statuses", methods=["GET"])
def update_fine_tune_job_statuses():
    updated_job_ids = check_statuses_of_fine_tune_jobs()
    return jsonify({"num_jobs": updated_job_ids})


@ML_BLUEPRINT.route("/latest_fine_tune", methods=["GET"])
def get_latest_fine_tune():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True
    )
    model_type = get_request_parameter("model_type", request, json=False, required=True)

    model_uuid, model_id = get_latest_custom_model(
        archetype_id=archetype_id, model_type=model_type
    )

    return jsonify({"model_uuid": model_uuid, "model_id": model_id})


@ML_BLUEPRINT.route("/fine_tune_job_timeline", methods=["GET"])
def get_fine_tune_job_timeline():
    fine_tune_id = get_request_parameter(
        "fine_tune_id", request, json=False, required=True
    )
    return jsonify(get_fine_tune_timeline(fine_tune_id))


@ML_BLUEPRINT.route("/create_profane_word", methods=["POST"])
def post_create_profane_word():
    from src.ml.services import create_profane_word

    words = get_request_parameter("words", request, json=False, required=True)
    profane_words = create_profane_word(words=words)
    return jsonify({"profane_word_id": profane_words.id})


@ML_BLUEPRINT.route("/get_config_completion", methods=["GET"])
def get_config_completion_endpoint():
    from model_import import StackRankedMessageGenerationConfiguration

    config_id = get_request_parameter("config_id", request, json=False, required=True)
    prospect_prompt = get_request_parameter(
        "prospect_prompt", request, json=False, required=True
    )

    configuration: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.get(config_id)
    )
    if configuration is None:
        return jsonify({"error": "Configuration not found"}), 400

    prompt = configuration.computed_prompt.format(prompt=prospect_prompt)

    response, few_shot_prompt = get_config_completion(configuration, prompt)

    return jsonify({"response": response, "few_shot_prompt": few_shot_prompt})


@ML_BLUEPRINT.route("/get_aree_fix/<message_id>", methods=["GET"])
def get_aree_fix_endpoint(message_id):
    # THIS NEEDS TO BE AUTHENTICATED EVENTUALLY
    completion = get_aree_fix_basic(int(message_id))
    return jsonify({"completion": completion})


@ML_BLUEPRINT.route("/generate_sequence_value_props", methods=["POST"])
def get_sequence_value_props_endpoint():

    company = get_request_parameter("company", request, json=True, required=True, parameter_type=str)
    selling_to = get_request_parameter("selling_to", request, json=True, required=True, parameter_type=str)
    selling_what = get_request_parameter("selling_what", request, json=True, required=True, parameter_type=str)
    num = get_request_parameter("num", request, json=True, required=True, parameter_type=int)

    result = get_sequence_value_props(company, selling_to, selling_what, num)

    return jsonify({"message": 'Success', 'data': result}), 200


@ML_BLUEPRINT.route("/generate_sequence_draft", methods=["POST"])
@require_user
def get_sequence_draft_endpoint(client_sdr_id: int):
    """Gets a sequence draft for a given value prop"""
    value_props = get_request_parameter("value_props", request, json=True, required=True, parameter_type=list)
    archetype_id = get_request_parameter("archetype_id", request, json=True, required=True, parameter_type=int)

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": 'Archetype not found'}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": 'Archetype does not belong to this user'}), 401

    try:
      result = get_sequence_draft(value_props, client_sdr_id, archetype_id)
      if not result:
          return jsonify({"message": "Generation rejected, please try again."}), 424
    except Exception as e:
      return jsonify({"message": f'Error: {str(e)}'}), 500

    return jsonify({"message": 'Success', 'data': result}), 200


@ML_BLUEPRINT.route("/icp_classification/icp_prompt/<int:archetype_id>", methods=["GET"])
@require_user
def get_icp_classification_prompt_by_archetype_id_endpoint(client_sdr_id: int, archetype_id: int):
    """Gets the ICP classification prompt for a given archetype"""
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": 'Archetype not found'}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": 'Archetype does not belong to this user'}), 401

    result = get_icp_classification_prompt_by_archetype_id(archetype_id)

    return jsonify({"message": 'Success', 'data': result}), 200


@ML_BLUEPRINT.route("/icp_classification/icp_prompt/<int:archetype_id>/request_update", methods=["POST"])
@require_user
def post_icp_classification_prompt_change_request_endpoint(client_sdr_id: int, archetype_id: int):
    """Requests an update to the ICP classification prompt for a given archetype

    This is a Wizard of Oz endpoint that will send a slack message
    """
    new_prompt = get_request_parameter("new_prompt", request, json=True, required=True, parameter_type=str)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": 'Archetype not found'}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": 'Archetype does not belong to this user'}), 401

    result, msg = post_icp_classification_prompt_change_request(client_sdr_id, archetype_id, new_prompt)
    if not result:
        return jsonify({"message": msg}), 400

    return jsonify({"message": 'Success', 'data': msg}), 200


@ML_BLUEPRINT.route("/icp_classification/icp_prompt/<int:archetype_id>", methods=["PATCH"])
@require_user
def patch_icp_classification_prompt_by_archetype_id_endpoint(client_sdr_id: int, archetype_id: int):
    """Updates the ICP classification prompt for a given archetype"""
    prompt = get_request_parameter("prompt", request, json=True, required=True, parameter_type=str)

    if prompt == "":
        return jsonify({"message": 'Prompt cannot be empty'}), 400

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": 'Archetype not found'}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": 'Archetype does not belong to this user'}), 401

    result = patch_icp_classification_prompt(archetype_id, prompt)

    return jsonify({"message": 'Success', 'data': result}), 200


@ML_BLUEPRINT.route("/icp_classification/trigger/<int:archetype_id>", methods=["POST"])
@require_user
def trigger_icp_classification_endpoint(client_sdr_id: int, archetype_id: int):
    """Runs ICP classification for prospects in a given archetype"""
    prospect_ids = get_request_parameter("prospect_ids", request, json=True, required=True, parameter_type=list)

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": 'Archetype not found'}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": 'Archetype does not belong to this user'}), 401

    result = trigger_icp_classification(client_sdr_id, archetype_id, prospect_ids)

    return jsonify({"message": 'Successfully triggered ICP classification. This may take a few minutes.'}), 200
