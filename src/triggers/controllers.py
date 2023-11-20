from flask import Blueprint
from src.authentication.decorators import require_user
from src.triggers.models import Trigger

TRIGGERS_BLUEPRINT = Blueprint("triggers", __name__)


@TRIGGERS_BLUEPRINT.route("/")
def index():
    return "OK", 200


@TRIGGERS_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_triggers(client_sdr_id: int):
    triggers: list = Trigger.query.filter_by(client_sdr_id=client_sdr_id).all()
    return {"triggers": [trigger.to_dict() for trigger in triggers]}, 200
