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
    client_id = get_request_parameter("client_id", request, json=True, required=True)

    status, job, message = initiate_fine_tune_job(
        client_id=client_id, message_ids=message_ids, model_type=GNLPModelType.OUTREACH
    )
    job.client_id = client_id
    db.session.add(job)
    db.session.commit()

    if status:
        return message, 200
    return message, 400


@ML_BLUEPRINT.route("/update_fine_tune_job_statuses", methods=["GET"])
def update_fine_tune_job_statuses():
    updated_job_ids = check_statuses_of_fine_tune_jobs()
    return jsonify({"num_jobs": updated_job_ids})


@ML_BLUEPRINT.route("/latest_fine_tune", methods=["GET"])
def get_latest_fine_tune():
    client_id = get_request_parameter("client_id", request, json=False, required=True)
    model_type = get_request_parameter("model_type", request, json=False, required=True)

    model_uuid, model_id = get_latest_custom_model(
        client_id=client_id, model_type=model_type
    )

    return jsonify({"model_uuid": model_uuid, "model_id": model_id})
