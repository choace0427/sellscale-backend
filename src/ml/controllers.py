from app import db

from flask import Blueprint, jsonify, request
from src.ml.fine_tuned_models import get_latest_custom_model
from src.ml.models import GNLPModelType
from src.ml.services import (
    check_statuses_of_fine_tune_jobs,
    create_upload_jsonl_file,
    initiate_fine_tune_job,
)

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

    status, message = initiate_fine_tune_job(
        archetype_id=archetype_id,
        message_ids=message_ids,
        model_type=GNLPModelType.OUTREACH,
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
