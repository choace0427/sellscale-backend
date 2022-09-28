from flask import Blueprint, jsonify, request
from src.prospecting.clay_run.clay_run_prospector import ClayRunProspector
from src.prospecting.clay_run.configs import ProspectingConfig
from src.utils.request_helpers import get_request_parameter

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)


@PROSPECTING_BLUEPRINT.route("/")
def index():
    location = get_request_parameter("location", request, json=True, required=True)
    headline = get_request_parameter("headline", request, json=True, required=True)
    industry = get_request_parameter("industry", request, json=True, required=True)
    experience = get_request_parameter("experience", request, json=True, required=True)

    prospector: ClayRunProspector = ClayRunProspector()

    config: ProspectingConfig = ProspectingConfig(
        location=location, headline=headline, industry=industry, experience=experience
    )

    data = prospector.prospect_sync(prospecting_config=config)

    print(data)

    return jsonify({"data": data})
