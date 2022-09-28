from flask import Blueprint, jsonify, request
from src.client.models import ClientArchetype
from src.client.services import get_client_archetype
from src.prospecting.clay_run.clay_run_prospector import ClayRunProspector
from src.prospecting.clay_run.configs import ProspectingConfig
from src.utils.request_helpers import get_request_parameter

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)


@PROSPECTING_BLUEPRINT.route("/")
def index():
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True
    )
    location = get_request_parameter("location", request, json=True, required=True)
    headline = get_request_parameter("headline", request, json=True, required=True)
    industry = get_request_parameter("industry", request, json=True, required=True)
    experience = get_request_parameter("experience", request, json=True, required=True)

    ca: ClientArchetype = get_client_archetype(client_archetype_id=archetype_id)
    if not ca:
        return "Archetype not found", 404

    prospector: ClayRunProspector = ClayRunProspector()

    config: ProspectingConfig = ProspectingConfig(
        location=location, headline=headline, industry=industry, experience=experience
    )

    data = prospector.prospect_sync(prospecting_config=config)

    return jsonify({"data": data})
