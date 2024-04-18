from typing import Optional

import requests
from app import db
import datetime
import os
from merge.client import Merge
from merge.resources.crm import (
    AccountDetails,
    Contact,
    CrmContactResponse,
    Account,
    CrmAccountResponse,
    Opportunity,
    OpportunityResponse,
    Stage,
    User,
)
from model_import import ClientSDR, Prospect, Client, Company, ProspectOverallStatus
from merge.resources.crm import (
    ContactsRetrieveRequestExpand,
    ContactRequest,
    EmailAddressRequest,
    AccountRequest,
    OpportunityRequest,
    PatchedOpportunityRequest,
    NoteRequest,
)

from src.merge_crm.models import ClientSyncCRM


class MergeIntegrator:
    """Merge Integrator used to integrate to CRMs using Merge"""

    def __init__(self):
        self.api_key = os.environ.get("MERGE_API_KEY") or ""

    def generate_link_token(self, client_sdr_id: int) -> Optional[str]:
        """Generate a link token to be used in Merge integration

        Args:
            client_sdr_id (int): Client SDR ID

        Returns:
            Optional[str]: Link token
        """
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Construct the payload
        body = {
            "end_user_origin_id": client.id,
            "end_user_organization_name": client.company,
            "end_user_email_address": client.contact_email,
            "categories": ["crm"],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Generate the link token
        link_token_response = requests.post(
            "https://api.merge.dev/api/integrations/create-link-token",
            data=body,
            headers=headers,
        )
        link_token = link_token_response.json().get("link_token")

        if not link_token:
            return None

        return link_token

    def retrieve_account_token(self, client_sdr_id: int, public_token: str) -> bool:
        """Retrieve the account token using the public token

        Args:
            client_sdr_id (int): Client SDR ID
            public_token (str): Public token

        Returns:
            bool: True if successful
        """
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Get the account_token
        headers = {"Authorization": f"Bearer {self.api_key}"}
        account_token_response = requests.get(
            f"https://api.merge.dev/api/integrations/account-token/{public_token}",
            headers=headers,
        )
        account_token = account_token_response.json().get("account_token")
        if not account_token:
            return False

        # Verify that we can get the account details
        mc: MergeClient = MergeClient(client_sdr_id=client_sdr_id)
        account = mc.get_crm_account_details()
        if not account:
            return None

        # Save the account token onto the client
        client.merge_crm_account_token = account_token
        db.session.add(client)
        db.session.commit()

        # Create a CRYM Sync Object
        client_sync_crm = ClientSyncCRM(
            client_id=client.id,
            initiating_client_sdr_id=client_sdr_id,
            account_token=account_token,
            crm_type=account.integration,
            status_mapping={},
            event_handlers={},
        )
        db.session.add(client_sync_crm)
        db.session.commit()

        return True

    def delete_integration(self, client_sdr_id: int) -> tuple[bool, str]:
        """Delete the integration for the client

        Args:
            client_sdr_id (int): Client SDR ID

        Returns:
            tuple[bool, str]: Success status and message
        """
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Make sure that we a CRM Sync object
        client_sync_crm = ClientSyncCRM.query.filter_by(client_id=client.id).first()
        if not client_sync_crm:
            return False, "No CRM Sync object found."

        # Make sure that the merge_crm_account_token is set
        if not client.merge_crm_account_token:
            return False, "No Client account token found."

        # Delete the Merge account
        merge: Merge = Merge(
            api_key=self.api_key, account_token=client.merge_crm_account_token
        )
        merge.crm.delete_account.delete()

        # Delete the CRM Sync object
        db.session.delete(client_sync_crm)
        db.session.commit()

        # Reset the account token
        client.merge_crm_account_token = None
        db.session.add(client)
        db.session.commit()

        return True, "Integration deleted."


class MergeClient:
    """Merge CRM Client"""

    def __init__(self, client_sdr_id: int):
        self.api_key = os.environ.get("MERGE_API_KEY") or ""

        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client_id = client_sdr.client_id
        client: Client = Client.query.get(client_id)
        self.account_token = client.merge_crm_account_token
        self.client = Merge(api_key=self.api_key, account_token=self.account_token)

    ###############################
    #         CRM METHODS         #
    ###############################

    def get_crm_account_details(self) -> AccountDetails:
        """Get the account details of the client's CRM

        Returns:
            AccountDetails: Account details
        """
        return self.client.crm.account_details.retrieve()

    def get_crm_type(self) -> str:
        """Get the CRM type of the client

        Returns:
            str: CRM type
        """
        account_details = self.client.crm.account_details.retrieve()
        return account_details.integration

    def get_crm_users(self) -> list[User]:
        """Get the list of users (SDRs) in the CRM

        Returns:
            list[User]: List of Users
        """
        return self.client.crm.users.list().results

    def get_crm_stages(self) -> list[Stage]:
        """Get the list of Stages that a Prospect may be in inside the CRM

        Returns:
            list[Stage]: List of Stages
        """
        return self.client.crm.stages.list().results

    ###############################
    #       CONTACT METHODS       #
    ###############################

    def find_contact_by_prospect_id(self, prospect_id: int) -> Optional[Contact]:
        """Finds the contact in the client's CRM using a prospect ID

        Args:
            prospect_id (int): Prospect ID

        Returns:
            Contact: Contact object
        """
        prospect: Prospect = Prospect.query.get(prospect_id)
        merge_contact_id: str = prospect.merge_contact_id
        if not merge_contact_id:
            return None

        # Find Contact
        try:
            contact = self.client.crm.contacts.retrieve(id=merge_contact_id)
        except:  # API returns 404 if contact is not found
            return None

        return contact

    def find_contact_by_email_address(self, email: str) -> Optional[Contact]:
        """Find contact by email address

        Args:
            email (str): Email address

        Returns:
            Contact: Contact object
        """
        # Find Contact
        try:
            contact = self.client.crm.contacts.list(
                email_addresses=email,
            )
        except:  # API returns 404 if contact is not found
            return None

        return contact

    def create_contact(self, prospect_id: int) -> tuple[Optional[str], str]:
        """Creates a contact in the client's CRM using a prospect ID

        Args:
            prospect_id (int): Prospect ID

        Returns:
            tuple[Optional[str], str]: Contact ID and message
        """
        # Get Prospect
        p: Prospect = Prospect.query.get(prospect_id)
        print(f"⚡️ Creating contact for {p.first_name} {p.last_name} (#{p.id})")

        # Get Client SDR
        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        # Check for existing Contact
        if p.merge_contact_id:
            contact = self.find_contact_by_prospect_id(prospect_id)
            if contact:
                return contact.id, "Contact already exists."
            else:
                return (
                    None,
                    "Contact not found - ID may be corrupted or prospect may be deleted.",
                )

        # If Account is not created, create Account
        if not p.merge_account_id:
            account_id, message = self.create_account(prospect_id)
            if not account_id:
                return None, f"Could not create Account: {message}"

        # Create Contact
        try:
            contact_res: CrmContactResponse = self.client.crm.contacts.create(
                model=ContactRequest(
                    first_name=p.first_name,
                    last_name=p.last_name,
                    addresses=[],
                    email_addresses=[
                        EmailAddressRequest(
                            email_address=p.email,
                            email_address_type="Work",
                        )
                    ],
                    phone_numbers=[],
                    last_activity_at=datetime.datetime.utcnow().isoformat(),
                    account=p.merge_account_id if p.merge_account_id else None,
                    owner=merge_user_id,
                ),
            )
        except Exception as e:
            return None, str(e)

        contact: Contact = contact_res.model
        p.merge_contact_id = contact.id
        db.session.add(p)
        db.session.commit()

        return contact.id, "Contact created."

    ###############################
    #       ACCOUNT METHODS       #
    ###############################

    def find_account_by_prospect_id(self, prospect_id: int) -> Optional[Account]:
        """Find Account by Prospect ID

        Args:
            prospect_id (int): Prospect ID

        Returns:
            Account: Account object
        """
        prospect: Prospect = Prospect.query.get(prospect_id)
        merge_account_id: str = prospect.merge_account_id
        if not merge_account_id:
            return None

        # Find Account
        try:
            account = self.client.crm.accounts.retrieve(id=merge_account_id)
        except:  # API returns 404 if account is not found
            return None

        return account

    def find_account_by_name(self, name: str) -> Optional[Account]:
        """Find Account by name

        Args:
            name (str): Account name

        Returns:
            Optional[Account]: Account object
        """
        # Find Account
        try:
            account = self.client.crm.accounts.list(
                name=name,
            )
            return account.results[0] if account.results else None
        except:  # API returns 404 if Account is not found
            return None

    def create_account(self, prospect_id: int) -> tuple[Optional[str], str]:
        """Create Account in the client's CRM

        Args:
            prospect_id (int): Prospect ID

        Returns:
            tuple[Optional[str], str]: Account ID and message
        """
        p: Prospect = Prospect.query.get(prospect_id)
        print("⚡️ Creating account for company: ", p.company)

        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        # Check for existing Account
        if p.merge_account_id:
            account = self.find_account_by_prospect_id(prospect_id)
            if account:
                return account.id, "Account already exists."
            else:
                return (
                    None,
                    "Account not found - ID may be corrupted or prospect may be deleted.",
                )

        # If we do not have a company ID, try to find the company
        if not p.company_id:
            from src.company.services import find_company_for_prospect

            find_company_for_prospect(prospect_id=prospect_id)
            p = Prospect.query.get(prospect_id)

        company: Company = Company.query.get(p.company_id)
        description = ""
        website_url = ""
        company_size = 0
        if company:
            description: str = company.description
            website_url: str = p.company_url
            company_size = p.employee_count

        # Create Account
        try:
            account_res: CrmAccountResponse = self.client.crm.accounts.create(
                model=AccountRequest(
                    name=p.company,
                    description="[Source: SellScale]\n" + description,
                    website=website_url,
                    number_of_employees=company_size,
                    last_activity_at=datetime.datetime.utcnow().isoformat(),
                    owner=merge_user_id,
                )
            )

            account: Account = account_res.model
            p.merge_account_id = account.id
            db.session.add(p)
            db.session.commit()

            return account.id, "Account created."
        except:
            return None, "Failed to create account."

    ###############################
    #    OPPORTUNITY METHODS      #
    ###############################

    def find_opportunity_by_prospect_id(self, prospect_id: int) -> Optional[str]:
        """Find Opportunity by Prospect ID

        Args:
            prospect_id (int): Prospect ID

        Returns:
            str: Opportunity ID
        """
        prospect: Prospect = Prospect.query.get(prospect_id)
        merge_opportunity_id: str = prospect.merge_opportunity_id
        if not merge_opportunity_id:
            return None

        # Find Opportunity
        try:
            opportunity = self.client.crm.opportunities.retrieve(
                id=merge_opportunity_id
            )
        except:
            return None

        return opportunity

    def create_opportunity(self, prospect_id: int) -> tuple[Optional[str], str]:
        """Create Opportunity in the client's CRM

        Args:
            prospect_id (int): Prospect ID

        Returns:
            tuple[Optional[str], str]: Opportunity ID and message
        """
        p: Prospect = Prospect.query.get(prospect_id)
        print(f"⚡️ Creating opportunity for {p.full_name} (#{p.id})")

        company: Company = Company.query.get(p.company_id)
        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        description = ""
        if company:
            description = company.description

        # If Account is not created, create Account
        if not p.merge_account_id:
            account_id, message = self.create_account(prospect_id)
            if not account_id:
                return None, f"Could not create Account: {message}"

        # If Contact is not created, create Contact
        if not p.merge_contact_id:
            contact_id, message = self.create_contact(prospect_id)
            if not contact_id:
                return None, f"Could not create Contact: {message}"

        # Check for existing Opportunity
        if p.merge_opportunity_id:
            opportunity = self.find_opportunity_by_prospect_id(prospect_id)
            if opportunity:
                return None, "Opportunity already exists."
            else:
                return (
                    None,
                    "Opportunity not found - ID may be corrupted or prospect may be deleted.",
                )

        # TODO(Aakash) - Add staging map here per client
        stage_mapping = {
            ProspectOverallStatus.ACTIVE_CONVO: "cf07e8fa-b5c2-4683-966e-4dc471963a32",
            ProspectOverallStatus.DEMO: "e927f7f3-3e66-43fd-b9a8-baf4f0ee4846",
        }
        status = stage_mapping.get(
            p.overall_status, "cf07e8fa-b5c2-4683-966e-4dc471963a32"
        )
        opportunity_value = 500

        # Create Opportunity
        try:
            opportunity_res: OpportunityResponse = self.client.crm.opportunities.create(
                model=OpportunityRequest(
                    name="[SellScale] " + p.company,
                    description="{first_name}, who is a {title} at {company}, is interested in our services.\n\nFit Reason:\n{fit_reason}\n\nDescription:\n{company_description}".format(
                        first_name=p.first_name,
                        title=p.title,
                        company=p.company,
                        fit_reason=p.icp_fit_reason,
                        company_description=description,
                    ),
                    amount=opportunity_value,
                    last_activity_at=datetime.datetime.utcnow().isoformat(),
                    account=p.merge_account_id,
                    contact=p.merge_contact_id,
                    status="OPEN",
                    owner=merge_user_id,
                )
            )

            opportunity: Opportunity = opportunity_res.model
            if opportunity.id:
                self.client.crm.opportunities.partial_update(
                    id=opportunity.id,
                    model=PatchedOpportunityRequest(stage=status),
                )

            p.merge_opportunity_id = opportunity.id
            p.contract_size = opportunity_value
            db.session.add(p)
            db.session.commit()

            return opportunity.id, "Opportunity created."
        except Exception as e:
            return None, str(e)

    def create_note(
        self,
        prospect_id,
        note,
        create_on_contact: bool = False,
        create_on_account: bool = False,
        create_on_opportunity: bool = False,
    ):
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

        owner_id = client_sdr.merge_user_id

        note = self.client.crm.notes.create(
            model=NoteRequest(
                content=note,
                owner=owner_id,
                contact=prospect.merge_contact_id if create_on_contact else None,
                account=prospect.merge_account_id if create_on_account else None,
                opportunity=(
                    prospect.merge_opportunity_id if create_on_opportunity else None
                ),
            )
        )

        return note
