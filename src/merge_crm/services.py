import datetime
from typing import Optional
from app import db
from sqlalchemy.orm import attributes

import requests
import os

import time
from src.client.models import ClientSDR, Client, Prospect
from merge.client import Merge
from src.merge_crm.models import ClientSyncCRM
from merge.resources.crm import (
    AddressRequest,
    ContactRequest,
    EmailAddressRequest,
    PhoneNumberRequest,
    LeadRequest,
    AccountRequest,
    LinkedAccountsListRequestCategory,
    ContactsListRequestExpand,
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

    # Create CRM Sync
    client_sync_crm = ClientSyncCRM(
        client_id=client.id,
        sync_type="leads_only",
        status_mapping={},
        event_handlers={},
    )
    db.session.add(client_sync_crm)
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


def update_crm_sync(
    client_sdr_id: int,
    sync_type: Optional[str],
    status_mapping: Optional[dict],
    event_handlers: Optional[dict],
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=client.id
    ).first()

    if not client_sync_crm:
        return None

    if sync_type:
        client_sync_crm.sync_type = sync_type
    if status_mapping:
        client_sync_crm.status_mapping = status_mapping
    if event_handlers:
        client_sync_crm.event_handlers = event_handlers

    db.session.add(client_sync_crm)
    db.session.commit()
    return client_sync_crm.to_dict()


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


def sync_data(client_sdr_id: int, endpoint: str, timestamp: str):

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    merge_client = Merge(api_key=API_KEY, account_token=client.merge_crm_account_token)

    while True:
        # Check the sync status
        sync_status = merge_client.crm.sync_status.list()
        sync_status = sync_status.dict().get("results")[0]

        # If the sync status is 'SYNCING', wait and then continue the loop
        if (
            sync_status["status"] == "SYNCING"
            and sync_status["is_initial_sync"] == "true"
        ):
            print("Data is still syncing, waiting...")
            time.sleep(10)
            continue

        # If the sync status is 'FAILED', 'DISABLED', raise an exception
        if sync_status["status"] in ["FAILED", "DISABLED", "PAUSED"]:
            raise Exception(f'Sync failed with status: {sync_status["status"]}')

        # If the sync status is 'SYNCED' or 'PARTIALLY_SYNCED', break the loop and proceed to data retrieval
        if sync_status["status"] in ["SYNCED", "PARTIALLY_SYNCED", "DONE"]:
            timestamp == sync_status["last_sync_start"]
            print("Data sync complete, proceeding to data retrieval...")
            break

    # Retrieve data from the specified common model endpoint
    data = getattr(merge_client, endpoint, timestamp)

    return data


def get_contacts(client_sdr_id: int):

    sync_data(
        client_sdr_id=client_sdr_id,
        endpoint="crm.contacts",
        timestamp="2022-01-01 00:00:00+00:00",
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_client = Merge(api_key=API_KEY, account_token=client.merge_crm_account_token)

    # if there is a next page, load it by passing `next` to the cursor argument
    start_date = datetime.datetime.fromisoformat("2000-01-01 00:00:00+00:00")
    response = merge_client.crm.contacts.list(created_after=start_date)
    while response.next is not None:
        response = merge_client.crm.contacts.list(
            cursor=response.next,
            created_after=start_date,
            expand=ContactsListRequestExpand.ACCOUNT,
        )

    contacts = response.dict().get("results")

    # contact_data = [
    #     get_contact_csm_data(client_sdr_id, contact.get("id")) for contact in contacts
    # ]

    # print(response.dict())

    # print(merge_client.crm.contacts.list(created_after=start_date).dict())
    print(merge_client.crm.opportunities.list(created_after=start_date).dict())
    print(merge_client.crm.stages.list(created_after=start_date).dict())
    print(merge_client.crm.leads.list(created_after=start_date).dict())
    print(merge_client.crm.tasks.list(created_after=start_date).dict())


def get_contact_csm_data(client_sdr_id: int, contact_id: str):

    from merge.client import Merge

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_client = Merge(api_key=API_KEY, account_token=client.merge_crm_account_token)
    response = merge_client.crm.contacts.meta_post_retrieve(
        remote_id=contact_id,
    )

    print(response.dict())


def get_operation_availability(client_sdr_id: int, operation_name: str):

    from merge.client import Merge

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_client = Merge(api_key=API_KEY, account_token=client.merge_crm_account_token)
    response = merge_client.crm.linked_accounts.list(
        category="crm",
        end_user_email_address=client.contact_email,
    )

    integrations = response.dict().get("results")

    operations = (
        integrations[0].get("integration", {}).get("available_model_operations", [])
        if len(integrations) > 0
        else []
    )

    parts = operation_name.split("_")
    if len(parts) != 2:
        return False

    model_name = parts[0]
    op_type = parts[1]

    # print(integrations, model_name, op_type)

    return any(
        [
            (
                model_name == operation.get("model_name")
                and op_type in operation.get("available_operations", [])
            )
            for operation in operations
        ]
    )


def create_contact(client_sdr_id: int, prospect_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    p: Prospect = Prospect.query.get(prospect_id)

    merge_client = Merge(api_key=API_KEY, account_token=client.merge_crm_account_token)
    # lead_res = merge_client.crm.leads.create(
    #     model={
    #         "leadSource": "SellScale",
    #         "title": p.title,
    #         "company": p.company,
    #         "firstName": p.first_name,
    #         "lastName": p.last_name,
    #         "addresses": [],
    #         "emailAddresses": [
    #             {
    #                 "emailAddress": p.email,
    #                 "emailAddressType": "Work",
    #             }
    #         ],
    #         "phoneNumbers": [],
    #         "convertedDate": datetime.datetime.utcnow().isoformat(),
    #     }
    # )

    if not get_operation_availability(client_sdr_id, "CRMContact"):
        return False, "Operation not available"

    contact_res = merge_client.crm.contacts.create(
        model=ContactRequest(
            first_name=p.first_name,
            last_name=p.last_name,
            addresses=[
                # AddressRequest(
                #     street_1="50 Bowling Green Dr",
                #     street_2="Golden Gate Park",
                #     city="San Francisco",
                #     state="CA",
                #     postal_code="94122",
                # )
            ],
            email_addresses=[
                EmailAddressRequest(
                    email_address=p.email,
                    email_address_type="Work",
                )
            ],
            phone_numbers=[
                # PhoneNumberRequest(
                #     phone_number="+3198675309",
                #     phone_number_type="Mobile",
                # )
            ],
            last_activity_at=datetime.datetime.utcnow().isoformat(),
        ),
    )

    print(contact_res)
    return True, "Contact created"


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
