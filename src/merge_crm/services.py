import datetime
from app import db
from sqlalchemy.orm import attributes

import requests
import os

from src.client.models import ClientSDR, Client
from merge.client import Merge
from merge.resources.crm import (
    AddressRequest,
    ContactRequest,
    EmailAddressRequest,
    PhoneNumberRequest,
    LeadRequest,
    AccountRequest,
)

API_KEY = os.environ.get("MERGE_API_KEY")


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


def retrieve_account_token(client_sdr_id: int, public_token: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    headers = {"Authorization": f"Bearer {API_KEY}"}

    account_token_url = (
        "https://api.merge.dev/api/integrations/account-token/{}".format(public_token)
    )
    account_token_result = requests.get(account_token_url, headers=headers)

    account_token = account_token_result.json().get("account_token")

    client.merge_crm_account_token = account_token
    db.session.add(client)
    db.session.commit()

    return account_token  # Save this in your database


def delete_account_token(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_crm_account_token = client.merge_crm_account_token

    data = None
    try:
        mergeClient = Merge(api_key=API_KEY, account_token=merge_crm_account_token)
        data = mergeClient.crm.delete_account.delete()
    except:
        pass

    client.merge_crm_account_token = None
    db.session.add(client)
    db.session.commit()

    return data


def get_integrations(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_crm_account_token = client.merge_crm_account_token

    if not merge_crm_account_token:
        return None

    mergeClient = Merge(api_key=API_KEY, account_token=merge_crm_account_token)

    data = mergeClient.crm.account_details.retrieve()

    return {
        "id": data.id,
        "integration": data.integration,
        "integration_slug": data.integration_slug,
        "category": data.category,
        "end_user_origin_id": data.end_user_origin_id,
        "end_user_organization_name": data.end_user_organization_name,
        "end_user_email_address": data.end_user_email_address,
        "status": data.status,
        "webhook_listener_url": data.webhook_listener_url,
        "is_duplicate": data.is_duplicate,
    }


def create_test_account(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_client = Merge(api_key=API_KEY, account_token=client.merge_crm_account_token)

    merge_client.crm.accounts.create(
        model=AccountRequest(
            name="SellScale Test",
            description="SellScale Test",
            industry="Software",
            website="https://sellscale.com",
            number_of_employees=100,
            last_activity_at=datetime.datetime.fromisoformat(
                "2022-02-10 00:00:00+00:00",
            ),
        ),
    )
