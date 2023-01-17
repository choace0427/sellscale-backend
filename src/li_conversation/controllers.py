import json
from flask import Blueprint, request, jsonify
from flask_csv import send_csv

LI_CONVERASTION_BLUEPRINT = Blueprint("li_conversation", __name__)


@LI_CONVERASTION_BLUEPRINT.route("/")
def get_li_conversation():

    return send_csv(
        [
            {"linkedin_url": "https://www.linkedin.com/in/abedelmalik/"},
            {"linkedin_url": "https://www.linkedin.com/in/dhavalbhatt/"},
            {"linkedin_url": "https://www.linkedin.com/in/randallrhall/"},
        ],
        "test.csv",
        ["linkedin_url"],
    )
