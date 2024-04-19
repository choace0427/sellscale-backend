import datetime
from typing import Optional
from app import db

import os

import time
from src.client.models import ClientSDR, Client, Prospect
from merge.client import Merge
from src.merge_crm.models import ClientSyncCRM
from merge.resources.crm import (
    ContactRequest,
    EmailAddressRequest,
    User,
    AccountRequest,
)
from model_import import Prospect
from src.merge_crm.merge_client import MergeIntegrator, MergeClient

API_KEY = os.environ.get("MERGE_API_KEY")


###############################
#     INTEGRATION METHODS     #
###############################


def create_link_token(client_sdr_id: int) -> tuple[bool, str]:
    """Creates a link token to be used in Merge integration

    Args:
        client_sdr_id (int): The SDR which initiated the integration

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and the link token
    """
    mi: MergeIntegrator = MergeIntegrator()
    link_token = mi.generate_link_token(client_sdr_id=client_sdr_id)

    return link_token is not None, link_token


def retrieve_account_token(client_sdr_id: int, public_token: str) -> tuple[bool, str]:
    """Retrieves the account token from Merge

    Args:
        client_sdr_id (int): The SDR which initiated the integration
        public_token (str): The public token generated from the link token

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and the account token
    """

    mi: MergeIntegrator = MergeIntegrator()
    account_token = mi.retrieve_account_token(
        client_sdr_id=client_sdr_id, public_token=public_token
    )

    return account_token is not None, account_token


def get_integration(client_sdr_id: int) -> dict:
    """Retrieves the integration details from Merge

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        dict: A dictionary containing the integration details
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_crm_account_token = client.merge_crm_account_token

    if not merge_crm_account_token:
        return None

    mc: MergeClient = MergeClient(client_sdr_id=client_sdr_id)
    data = mc.get_crm_account_details()

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


def delete_integration(client_sdr_id: int) -> tuple[bool, str]:
    """Deletes the integration from Merge

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    mi: MergeIntegrator = MergeIntegrator()
    success, message = mi.delete_integration(client_sdr_id=client_sdr_id)

    return success, message


# TODO: This might differ depending on the CRM
def create_test_account(client_sdr_id: int) -> bool:
    """Creates a test account in the CRM

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        bool: A boolean indicating success
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    merge_client = Merge(api_key=API_KEY, account_token=client.merge_crm_account_token)
    merge_client.crm.accounts.create(
        model=AccountRequest(
            name="SellScale Test",
            description="Congratulations on integrating with SellScale!",
            industry="Software",
            website="https://sellscale.com",
            number_of_employees=100,
            last_activity_at=datetime.datetime.fromisoformat(
                "2022-02-10 00:00:00+00:00",
            ),
        ),
    )

    return True


###############################
#      CRM SYNC METHODS       #
###############################


# Needs Documentation
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


# Needs Documentation
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


def get_crm_users(client_sdr_id: int) -> list[dict]:
    """Gets the users from the CRM

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        list[dict]: A list of users from the CRM
    """
    mc: MergeClient = MergeClient(client_sdr_id=client_sdr_id)
    users: list[User] = mc.get_crm_users()

    return [user.dict() for user in users]


def sync_user_to_sdr(client_sdr_id: int, merge_user_id: Optional[str] = None) -> bool:
    """Updates the connection between the SDR and the CRM user using the Merge ID

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client
        merge_user_id (str): The ID of the CRM user in Merge

    Returns:
        bool: A boolean indicating success
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    client_sdr.merge_user_id = merge_user_id
    db.session.commit()

    return True


###############################
#    UNCATEGORIZED METHODS    #
###############################


# TODO: Fix this and move it into the MergeClient class
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


# TODO: Make this use the MergeClient class
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


def create_opportunity_from_prospect_id(
    client_sdr_id: int, prospect_id: int
) -> tuple[bool, str]:
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id:
        return False, "Prospect not found"

    mc: MergeClient = MergeClient(client_sdr_id)
    success = mc.create_opportunity(prospect_id)

    if not success:
        return False, "Opportunity not created"

    return True, "Opportunity created"
