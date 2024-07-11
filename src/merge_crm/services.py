import datetime
from typing import Optional
from app import db, celery

import os

import time
from src.client.models import ClientSDR, Client, Prospect
from merge.client import Merge
from src.email_outbound.models import (
    EMAIL_ACTIVE_CONVO_POSITIVE_STATUSES,
    ProspectEmail,
)
from src.merge_crm.models import ClientSyncCRM
from src.merge_crm.models import CRMContact
from merge.resources.crm import (
    ContactRequest,
    EmailAddressRequest,
    User,
    AccountRequest,
    ModelOperation,
)
from model_import import Prospect
from src.merge_crm.merge_client import MergeIntegrator, MergeClient
from src.prospecting.models import (
    LINKEDIN_ACTIVE_CONVO_POSITIVE_STATUSES,
    ProspectOverallStatus,
    ProspectStatus,
)

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


def get_client_sync_crm(client_sdr_id: int) -> dict:
    """Gets the CRM sync details for the client

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        dict: A dictionary containing the CRM sync details
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=client_sdr.client_id
    ).first()

    return client_sync_crm.to_dict() if client_sync_crm else None


def get_client_sync_crm_supported_models(client_sdr_id: int) -> list[str]:
    """Gets the supported models that the CRM supports, along with their operations

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        list[str]: A list of supported model names
    """
    mc: MergeClient = MergeClient(client_sdr_id)
    supported_models: list[ModelOperation] = mc.get_crm_supported_model_operations()
    supported_model_names: list[str] = [model.model_name for model in supported_models]

    return supported_model_names


def update_syncable_models(
    client_sdr_id: int,
    lead_sync: Optional[bool] = False,
    contact_sync: Optional[bool] = False,
    account_sync: Optional[bool] = False,
    opportunity_sync: Optional[bool] = False,
) -> bool:
    """Updates the syncable models for the client

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client
        lead_sync (Optional[bool], optional): Whether we are syncing Leads. Defaults to False.
        contact_sync (Optional[bool], optional): Whether we are syncing Contacts. Defaults to False.
        account_sync (Optional[bool], optional): Whether we are syncing Accounts. Defaults to False.
        opportunity_sync (Optional[bool], optional): Whether we are syncing Opportunities. Defaults to False.

    Returns:
        bool: A boolean indicating success
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=client.id
    ).first()

    client_sync_crm.lead_sync = lead_sync
    client_sync_crm.contact_sync = contact_sync
    client_sync_crm.account_sync = account_sync
    client_sync_crm.opportunity_sync = opportunity_sync

    db.session.add(client_sync_crm)
    db.session.commit()

    return True


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

def poll_crm_contacts():
    # Get all client ids, loop through them and get all contacts
    client_ids = db.session.query(Client.id).all()
    for client_id_tuple in client_ids:
        try:
            client_id = client_id_tuple[0]
            #check if client has a merge sync

            client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
                client_id=client_id
            ).first()
            if not client_sync_crm:
                continue
            # Choose a random client SDR from the client. This is a weird convention for the MergeClient class
            client_sdr_id = db.session.query(ClientSDR.id).filter(ClientSDR.client_id == client_id).first()[0]
            contacts = get_crm_user_contacts(client_sdr_id)
            
            for contact in contacts:
                existing_contact = db.session.query(CRMContact).filter_by(
                    first_name=contact['first_name'],
                    last_name=contact['last_name'],
                    client_id=client_id
                ).first()
                
                if not existing_contact:
                    new_contact = CRMContact(
                        first_name=contact['first_name'],
                        last_name=contact['last_name'],
                        do_not_contact=False,
                        company=contact['account']['name'] if contact.get('account') else None,
                        industry=contact['account']['industry'] if contact.get('account') else None,
                        company_url=contact['account']['website'] if contact.get('account') else None,
                        email_addresses=contact['email_addresses'],
                        client_id=client_id
                    )
                    db.session.add(new_contact)
            
            db.session.commit()
        except Exception as e:
            print(f"Error getting contacts for client {client_id}: {e}")
            continue

def update_dnc_status(client_sdr_id: int, contact_id: int, do_not_contact: bool) -> tuple[bool, str]:
    """Updates the Do Not Contact (DNC) status of a contact for a given client SDR.

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client.
        contact_id (int): The ID of the contact whose DNC status is to be updated.
        do_not_contact (bool): The new DNC status to be set.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message.
    """
    try:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        if not client_sdr:
            return False, "Client SDR not found"

        contact: CRMContact = CRMContact.query.get(contact_id)
        if not contact or contact.client_id != client_sdr.client_id:
            return False, "Contact not found or does not belong to the client"

        contact.do_not_contact = do_not_contact
        db.session.commit()
        return True, "DNC status updated successfully"
    except Exception as e:
        db.session.rollback()
        return False, f"Error updating DNC status: {e}"


def get_crm_user_contacts_from_db(client_sdr_id: int) -> list[dict]:
    """Gets the contacts from the CRM

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        list[dict]: A list of contacts from the CRM
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    contacts: list[CRMContact] = db.session.query(CRMContact).filter_by(client_id=client.id).all()
    return [contact.to_dict() for contact in contacts]


def get_crm_user_contacts(client_sdr_id: int) -> list[dict]:
    """Gets the contacts from the CRM

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        list[dict]: A list of contacts from the CRM
    """
    mc: MergeClient = MergeClient(client_sdr_id=client_sdr_id)
    contacts: list[ContactRequest] = []
    
    for contact in mc.get_all_crm_contacts():
        if contact.first_name is not None:
            contacts.append(contact)
    return [
        {
            **contact.dict(),
            "email_addresses": [email.email_address for email in contact.email_addresses] if contact.email_addresses else []
        }
        for contact in contacts
    ]

def sync_sdr_to_crm_user(
    client_sdr_id: int, merge_user_id: Optional[str] = None
) -> bool:
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


def get_crm_stages(client_sdr_id: int) -> list[dict]:
    """Gets the stages from the CRM

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client

    Returns:
        list[dict]: A list of stages from the CRM
    """
    mc: MergeClient = MergeClient(client_sdr_id=client_sdr_id)
    stages = mc.get_crm_stages()

    return [stage.dict() for stage in stages]


def sync_sellscale_to_crm_stages(
    client_sdr_id: int, stage_mapping: Optional[dict] = {}
) -> bool:
    """Syncs the stages from SellScale to the CRM

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client
        stage_mapping (dict): A dictionary containing the stage mapping

    Returns:
        bool: A boolean indicating success
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    # Get the ClientSyncCRM object
    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=client.id
    ).first()

    # Update the status mapping
    client_sync_crm.status_mapping = stage_mapping
    db.session.add(client_sync_crm)
    db.session.commit()

    return True


def save_sellscale_crm_event_handler(
    client_sdr_id: int, event_handlers: Optional[dict] = {}
) -> bool:
    """Saves the event handlers for the SDR

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client
        event_handlers (dict): A dictionary containing the event handlers

    Returns:
        bool: A boolean indicating success
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    # Get the ClientSyncCRM object
    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=client.id
    ).first()

    # Update the event handlers
    client_sync_crm.event_handlers = event_handlers
    db.session.add(client_sync_crm)
    db.session.commit()

    return True


def check_and_use_crm_event_handler(
    client_sdr_id: int, prospect_id: int, overall_status: ProspectOverallStatus
) -> tuple[bool, str]:
    """Checks if there is an event handler for the given status and triggers it

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client
        prospect_id (int): The ID of the Prospect
        overall_status (ProspectOverallStatus): The status of the Prospect

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """

    def is_prospect_status_active_convo_positive(prospect_id: int) -> bool:
        """Checks if the Prospect status is positive

        Args:
            prospect_id (int): The ID of the Prospect

        Returns:
            bool: A boolean indicating if the Prospect status is positive
        """
        prospect: Prospect = Prospect.query.get(prospect_id)
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect.approved_prospect_email_id
        )

        # Is LinkedIn status positive?
        if prospect.status in LINKEDIN_ACTIVE_CONVO_POSITIVE_STATUSES:
            return True

        # Is Email status positive?
        if (
            prospect_email
            and prospect_email.outreach_status in EMAIL_ACTIVE_CONVO_POSITIVE_STATUSES
        ):
            return True

        return False

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    # 0a. Get the ClientSyncCRM object
    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=client.id
    ).first()
    if not client_sync_crm:
        return False, "ClientSyncCRM not found"

    # 0b. Get the prospect
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.merge_opportunity_id:
        return False, "Prospect already synced"

    # 1. Check if there is an event handler for the given status
    event_handler = client_sync_crm.event_handlers.get(overall_status.value)
    if not event_handler:
        # Check for a "positive reply" event handler if the status is "ACTIVE_CONVO"
        positive_reply_event_handler = client_sync_crm.event_handlers.get(
            "ACTIVE_CONVO_POSITIVE_REPLY"
        )
        if (
            positive_reply_event_handler
            and overall_status == ProspectOverallStatus.ACTIVE_CONVO
        ):
            is_positive = is_prospect_status_active_convo_positive(prospect_id)
            if is_positive:
                event_handler = positive_reply_event_handler

    if not event_handler:
        return False, "No event handler found for the given status"

    # 1c. This is a bit of a hack to handle cases where a user may want us to sync
    # to non-opportunity models. We still want to sync the prospect to the CRM
    # but don't want to accidentally send to a stage. In theory, we should never
    # even try to create a CAO if we're not syncing opportunities, but this is
    # a safety net.
    if event_handler == "LEAD_ONLY":
        event_handler = None

    # 2. Trigger the event handler
    success, message = upload_prospect_to_crm(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        stage_id_override=event_handler,
    )

    # 3. Send slack message
    if success:
        from src.utils.slack import send_slack_message, URL_MAP

        mc: MergeClient = MergeClient(client_sdr_id)
        mc_details = mc.get_crm_account_details()
        opportunity_details = mc.find_opportunity_by_prospect_id(prospect_id)
        opportunity_name = opportunity_details.name
        send_slack_message(
            message=f"Added new opportunity into {client.company}'s CRM\nUser: {client_sdr.name}\nCRM: {mc_details.integration}\nProspect: {prospect.full_name} (#{prospect.id})\nEvent: Moved to {overall_status.value}\n\nOpportunity: {opportunity_name}",
            webhook_urls=[URL_MAP["ops-crm-sync-updates"]],
        )

    return success, message


###############################
#       POLLING METHODS       #
###############################


@celery.task
def poll_crm_opportunities() -> None:
    """Polls and update opportunities from the CRM

    Returns:
        None
    """
    # Get all unique Merge Opportunity IDs from Prospects
    sql_query = """
        SELECT DISTINCT
            prospect.merge_opportunity_id
        FROM
            prospect
        WHERE
            merge_opportunity_id IS NOT NULL;
    """
    result = db.engine.execute(sql_query).fetchall()
    merge_opportunity_ids = [row[0] for row in result]

    for opportunity_id in merge_opportunity_ids:
        print("Processing opportunity:", opportunity_id)
        # Get the Prospects that are linked to this opportunity
        prospects: list[Prospect] = Prospect.query.filter(
            Prospect.merge_opportunity_id == opportunity_id
        ).all()

        # Get the SDR that is linked to the first Prospect
        client_sdr_id = prospects[0].client_sdr_id
        crm: MergeClient = MergeClient(client_sdr_id)

        # Get the latest opportunity details from the CRM
        opportunity = crm.find_opportunity_by_opportunity_id(opportunity_id)
        if not opportunity:
            # A desync has occured, remove the opportunity ID from the Prospects
            print("Opportunity not found, removing from Prospects.")
            update_data = [
                {
                    "id": prospect.id,
                    "merge_opportunity_id": None,
                }
                for prospect in prospects
            ]
            db.session.bulk_update_mappings(Prospect, update_data)
            continue

        # Get relevant details from the opportunity #TODO: Add more here?
        amount = opportunity.amount

        # Update the Prospects with the latest opportunity details
        print("Updating Prospects with opportunity details.")
        update_data = [
            {
                "id": prospect.id,
                "contract_size": amount,
            }
            for prospect in prospects
        ]
        db.session.bulk_update_mappings(Prospect, update_data)

    db.session.commit()
    return


###############################
#      UPLOADING METHODS      #
###############################


def upload_prospect_to_crm(
    client_sdr_id: int, prospect_id: int, stage_id_override: Optional[str] = None
) -> tuple[bool, str]:
    """Uploads a Prospect to the CRM using whichever models are selected in the CRM sync

    Args:
        client_sdr_id (int): The ID of the SDR, used for retrieving the client
        prospect_id (int): The ID of the Prospect
        stage_id_override (Optional[str], optional): The stage ID to override the default stage. Defaults to None.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
        client_id=client.id
    ).first()
    if not client_sync_crm:
        return False, "ClientSyncCRM not found"

    mc: MergeClient = MergeClient(client_sdr_id)

    # Lead Sync
    if client_sync_crm.lead_sync:
        id, message = mc.create_lead(prospect_id=prospect_id)
        if not id:
            return False, message

    # Account Sync
    if client_sync_crm.account_sync:
        id, message = mc.create_account(prospect_id=prospect_id)
        if not id:
            return False, message

    # Contact Sync
    if client_sync_crm.contact_sync:
        id, message = mc.create_contact(prospect_id=prospect_id)
        if not id:
            return False, message

    # Opportunity Sync
    if client_sync_crm.opportunity_sync:
        id, message = mc.create_opportunity(
            prospect_id=prospect_id, stage_id_override=stage_id_override
        )
        if not id:
            return False, message

    # Note sync (it doesn't make sense to sync a note if we're not syncing anything else)
    if (
        client_sync_crm.account_sync
        or client_sync_crm.contact_sync
        or client_sync_crm.opportunity_sync
    ):
        id, message = mc.create_note(prospect_id=prospect_id)
        if not id:
            return False, message

    return True, "Prospect uploaded"
