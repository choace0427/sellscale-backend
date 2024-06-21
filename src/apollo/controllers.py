from flask import Blueprint, jsonify, request

from src.apollo.services import save_apollo_cookies
from src.utils.request_helpers import get_request_parameter


APOLLO_REQUESTS = Blueprint("apollo", __name__)


@APOLLO_REQUESTS.route("/cookies", methods=["GET"])
def get_apollo_cookies():
    """
    Gets Apollo cookies.
    """
    cookies, csrf_token = get_apollo_cookies()

    if not cookies:
        return (
            jsonify({"status": "error", "message": "Error getting Apollo cookies."}),
            500,
        )

    return (
        jsonify(
            {
                "status": "success",
                "data": {"cookies": cookies, "csrf_token": csrf_token},
            }
        ),
        200,
    )


@APOLLO_REQUESTS.route("/cookies", methods=["POST"])
def post_save_apollo_cookies():
    """
    Saves Apollo cookies.
    """
    cookies = get_request_parameter(
        "cookies", request, json=True, required=True, parameter_type=str
    )
    csrf_token = get_request_parameter(
        "csrf_token", request, json=True, required=True, parameter_type=str
    )

    if not save_apollo_cookies(cookies=cookies, csrf_token=csrf_token):
        return (
            jsonify({"status": "error", "message": "Error saving Apollo cookies."}),
            500,
        )

    return jsonify({"status": "success", "message": "Apollo cookies saved."}), 200
