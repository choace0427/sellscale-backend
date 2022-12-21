from flask import Blueprint, request
from src.ml_adversary.models import AdversaryTrainingPoint
from src.ml_adversary.services import (
    create_adversary_training_point, 
    toggle_adversary_training_point)
from src.utils.request_helpers import get_request_parameter

ML_ADVERSARY_BLUEPRINT = Blueprint("adversary", __name__)


@ML_ADVERSARY_BLUEPRINT.route("/train", methods=["POST"])
def train_adversary():
    pass


@ML_ADVERSARY_BLUEPRINT.route("/create", methods=["POST"])
def create_adversary(generated_message_id: int, mistake: str, fix: str):
    pass


@ML_ADVERSARY_BLUEPRINT.route("/toggle_point", methods=["POST"])
def toggle_training_point(training_point_id: int, toggle_on: bool = False):
    pass


@ML_ADVERSARY_BLUEPRINT.route("/preview_fix", methods=["POST"])
def preview_fix(completion: str, fix: str):
    pass


@ML_ADVERSARY_BLUEPRINT.route("/edit", methods=["POST"])
def edit_training_point(training_point_id: int, mistake: str, fix: str):
    pass
