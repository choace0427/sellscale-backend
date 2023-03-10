from app import db

from flask import Blueprint, jsonify, request
from src.ml.fine_tuned_models import get_latest_custom_model
from src.ml.models import GNLPModelType
from src.ml.services import (
    check_statuses_of_fine_tune_jobs,
    get_fine_tune_timeline,
    initiate_fine_tune_job,
    get_aree_fix_basic
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
    completion = get_aree_fix_basic(message_id)
    return jsonify({"completion": completion})
