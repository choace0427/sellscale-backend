from model_import import Prospect, ProspectOverallStatus, Client
from app import db
from src.sight_inbox.services import DEMO_SET
import requests


def handle_webhook(
    prospect_id: int,
    previous_status: ProspectOverallStatus,
    new_status: ProspectOverallStatus,
):
    try:
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            return
        client_id: int = prospect.client_id
        client: Client = Client.query.get(client_id)
        if not client:
            return

        payload = {
            "prospect_full_name": prospect.full_name,
            "prospect_email": prospect.email,
            "prospect_linkedin_url": prospect.linkedin_url,
            "prospect_title": prospect.title,
            "prospect_location": prospect.prospect_location,
            "prospect_status": prospect.overall_status.value,
            "prospect_direct_link": "https://app.sellscale.com/prospects/" + str(prospect_id),
            "company": prospect.company,
            "company_url": prospect.company_url,
            "company_location": prospect.company_location,
            "company_colloquialized_name": prospect.colloquialized_company,
        }

        if (
            previous_status != ProspectOverallStatus.DEMO
            and new_status == ProspectOverallStatus.DEMO
        ):
            if client.on_demo_set_webhook:
                requests.post(client.on_demo_set_webhook, json=payload)

        if (
            previous_status != ProspectOverallStatus.ACTIVE_CONVO
            and new_status == ProspectOverallStatus.ACTIVE_CONVO
        ):
            if client.on_active_convo_webhook:
                requests.post(client.on_active_convo_webhook, json=payload)
    except Exception as e:
        print(f"Error in handle_webhook: {e}")
        return
