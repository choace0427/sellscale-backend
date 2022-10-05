from app import db

from flask import Blueprint, jsonify, request
from src.ml.services import create_upload_jsonl_file, initiate_fine_tune_job

from src.message_generation.models import GeneratedMessage
from src.utils.request_helpers import get_request_parameter

ML_BLUEPRINT = Blueprint("ml", __name__)


@ML_BLUEPRINT.route("/", methods=["POST"])
def index():
    message_ids = get_request_parameter(
        "message_ids", request, json=True, required=True
    )
    client_id = get_request_parameter("client_id", request, json=True, required=True)

    status, job, message = initiate_fine_tune_job(
        client_id=client_id, message_ids=message_ids
    )
    job.client_id = client_id
    db.session.add(job)
    db.session.commit()

    if status:
        return message, 200
    return message, 400
