from flask import Blueprint

from .services import get_echo

ECHO_BLUEPRINT = Blueprint("echo", __name__)


@ECHO_BLUEPRINT.route("/")
def index():
    get_echo()
    return "OK", 200
