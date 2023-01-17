import json
from flask import Blueprint, request, jsonify
from flask_csv import send_csv
from model_import import Prospect
from datetime import datetime, timedelta

LI_CONVERASTION_BLUEPRINT = Blueprint("li_conversation", __name__)


@LI_CONVERASTION_BLUEPRINT.route("/<client_id>")
def get_li_conversation(client_id):
    prospects = Prospect.query.filter(
        Prospect.client_id == client_id,
        Prospect.li_last_message_timestamp > datetime.now() - timedelta(days=1),
    ).all()

    linkedin_urls = [
        {"linkedin_url": prospect.linkedin_url}
        for prospect in prospects
        if prospect.linkedin_url
    ]

    return send_csv(
        linkedin_urls,
        "test.csv",
        ["linkedin_url"],
    )
