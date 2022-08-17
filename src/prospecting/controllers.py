from flask import Blueprint, jsonify
from src.prospecting.clay_run.clay_run_prospector import ClayRunProspector
from src.prospecting.clay_run.configs import ProspectingConfig

PROSPECTING_BLUEPRINT = Blueprint('prospect', __name__)


@PROSPECTING_BLUEPRINT.route("/")
def index():
    prospector: ClayRunProspector = ClayRunProspector()

    config: ProspectingConfig = ProspectingConfig(
        location='San Francisco',
        headline='CTO',
        industry='Technology',
        experience='Technology'
    )

    # data = []
    data = prospector.prospect_sync(
        prospecting_config=config
    )

    return jsonify({'data': data})