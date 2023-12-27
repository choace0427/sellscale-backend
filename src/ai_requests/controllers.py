from flask import Blueprint
from src.ai_requests.models import AIRequest

AI_REQUESTS = Blueprint("ai_request", __name__)


@AI_REQUESTS.route("/")
def index():
    return "OK", 200
