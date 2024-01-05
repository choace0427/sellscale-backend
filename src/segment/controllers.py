from flask import Blueprint
from src.segment.models import Segment

SEGMENT_BLUEPRINT = Blueprint("segment", __name__)


@SEGMENT_BLUEPRINT.route("/")
def index():
    return "OK", 200
