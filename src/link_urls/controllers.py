from flask import Blueprint, request
from app import db
from src.authentication.decorators import require_user
from src.link_urls.services import add_url_link, get_url_stats
from src.utils.request_helpers import get_request_parameter

LINK_URL_BLUEPRINT = Blueprint("link_url", __name__)


@LINK_URL_BLUEPRINT.route("/")
def index():
    return "OK", 200


@LINK_URL_BLUEPRINT.route("/create", methods=["POST"])
def post_create_url_endpoint():

    url = get_request_parameter("url", request, json=True, required=True)
    description = (
        get_request_parameter("description", request, json=True, required=False) or url
    )

    url_id, tiny_url = add_url_link(None, url, description)
    return {
        "success": True,
        "data": {
            "url_id": url_id,
            "tiny_url": tiny_url,
        },
    }, 200


@LINK_URL_BLUEPRINT.route("/stats", methods=["GET"])
def get_url_stats_endpoint():

    url_id = get_request_parameter("url_id", request, json=False, required=True)
    stats = get_url_stats(url_id)
    return {
        "success": True,
        "data": stats,
    }, 200
