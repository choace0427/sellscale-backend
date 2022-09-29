from app import db

from flask import Blueprint, request
from src.research.linkedin.services import get_research_and_bullet_points_new
from src.message_generation.services import (
    generate_outreaches_for_batch_of_prospects,
)
from src.utils.request_helpers import get_request_parameter
from tqdm import tqdm

MESSAGE_GENERATION_BLUEPRINT = Blueprint("message_generation", __name__)


@MESSAGE_GENERATION_BLUEPRINT.route("/batch", methods=["POST"])
def index():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    # researching prospects
    print("Research prospects ...")
    for prospect_id in tqdm(prospect_ids):
        get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

    # generating messages
    print("Generated messages ...")
    generate_outreaches_for_batch_of_prospects(prospect_list=prospect_ids)

    return "OK", 200
