from app import db
from sqlalchemy.orm import attributes

import requests

from src.client.models import ClientSDR, Client

API_KEY = "Fi3ktbxGZVozZaWLk4IVDjqdL15tBRNUFEFeykpnxpiBg4fLhaI63w"


# Replace api_key with your Merge production API Key
def create_link_token(client_sdr_id):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    organization_id = client.id
    organization_name = client.company
    email_address = client_sdr.email

    body = {
        "end_user_origin_id": client_sdr_id,  # your user's id
        "end_user_organization_name": organization_name,  # your user's organization name
        "end_user_email_address": email_address,  # your user's email address
        "categories": [
            # "hris",
            # "ats",
            # "accounting",
            # "ticketing",
            "crm",
        ],  # choose your category
    }

    headers = {"Authorization": f"Bearer {API_KEY}"}

    link_token_url = "https://api.merge.dev/api/integrations/create-link-token"
    link_token_result = requests.post(link_token_url, data=body, headers=headers)
    link_token = link_token_result.json().get("link_token")

    return link_token
