from src.campaigns.controllers import CAMPAIGN_BLUEPRINT
from src.campaigns.autopilot.services import collect_and_generate_all_autopilot_campaigns

@CAMPAIGN_BLUEPRINT.route("/autopilot/generate_all_campaigns", methods=["POST"])
def generate_all_autopilot_campaigns_endpoint():
    collect_and_generate_all_autopilot_campaigns()
    return "OK", 200