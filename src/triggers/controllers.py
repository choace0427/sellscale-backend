from flask import Blueprint
from src.triggers.models import Trigger

TRIGGERS_BLUEPRINT = Blueprint("triggers", __name__)


@TRIGGERS_BLUEPRINT.route("/")
def index():
    return "OK", 200
