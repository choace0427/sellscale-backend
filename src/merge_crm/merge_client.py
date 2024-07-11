from typing import Optional

import requests
from app import db, celery
import datetime
import os
from merge.client import Merge
from merge.resources.crm import (
    AccountDetails,
    Contact,
    CrmContactResponse,
    ContactsListRequestExpand,
    Account,
    CrmAccountResponse,
    Opportunity,
    OpportunityResponse,
    Stage,
    User,
    Lead,
    ContactRequest,
    EmailAddressRequest,
    AccountRequest,
    OpportunityRequest,
    PatchedOpportunityRequest,
    NoteRequest,
    NoteResponse,
    Note,
    AccountDetailsAndActions,
    AccountDetailsAndActionsIntegration,
    ModelOperation,
    LeadRequest,
    LeadResponse,
    PaginatedLeadList,
    Engagement,
    EngagementType,
    EngagementResponse,
    EngagementRequest,
)

from model_import import ClientSDR, Prospect, Client, Company, ProspectOverallStatus

from src.client.models import ClientArchetype
from src.merge_crm.models import ClientSyncCRM
from src.prospecting.services import get_prospect_overall_history


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
        mc: MergeClient = MergeClient(
            client_sdr_id=client_sdr_id, account_token=account_token
        )
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
            account_id=account.id,
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

    def __init__(self, client_sdr_id: int, account_token: Optional[str] = None):
        self.api_key = os.environ.get("MERGE_API_KEY") or ""

        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client_id = client_sdr.client_id
        client: Client = Client.query.get(client_id)
        client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
            client_id=client_id
        ).first()

        # Either use the provided account token or the client's account token
        if account_token:
            self.account_token = account_token
        else:
            self.account_token = client.merge_crm_account_token

        self.client = Merge(api_key=self.api_key, account_token=self.account_token)
        self.client_sync_crm = client_sync_crm

    def is_allowable(model_name: str):
        """Decorator to check if the model is allowed to be synced"""

        def decorator(method):
            def wrapper(self, *args, **kwargs):
                print(f"Checking if model {model_name} is supported...")

                self: MergeClient = self  # Typing hack
                allowable_models = self.get_crm_supported_model_operations()
                allowable_model_names = [model.model_name for model in allowable_models]
                if model_name not in allowable_model_names:
                    raise Exception(
                        f"Model {model_name} is not supported with this CRM integration {self.client_sync_crm.crm_type}."
                    )

                print(f"Model {model_name} is supported!")
                return method(self, *args, **kwargs)

            return wrapper

        return decorator

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

    def get_crm_engagements(self) -> list[Engagement]:
        """Get the list of Engagements in the CRM

        Returns:
            list[Engagement]: List of Engagements
        """
        return self.client.crm.engagements.list().results

    def get_crm_engagement_types(self) -> list[EngagementType]:
        """Get the list of Engagement types in the CRM

        Returns:
            list[str]: List of Engagement types
        """
        return self.client.crm.engagement_types.list().results

    def get_crm_supported_model_operations(
        self,
    ) -> list[ModelOperation]:
        """Get the list of supported operations in the CRM

        Returns:
            list[ModelOperation]: List of ModelOperations
        """
        try:
            account_details: AccountDetailsAndActions = (
                self.client.crm.linked_accounts.list(
                    id=self.client_sync_crm.account_id
                ).results
            )[0]
        except IndexError as e:
            print(f"IndexError: {str(e)} - No linked accounts found for the given account ID.")
            return []
        except Exception as e:
            print(f"Exception: {str(e)} - An error occurred while retrieving linked accounts.")
            return []

        try:
            integration: AccountDetailsAndActionsIntegration = account_details.integration
            operations: list[ModelOperation] = integration.available_model_operations
        except AttributeError as e:
            print(f"AttributeError: {str(e)} - Failed to retrieve integration details or model operations.")
            return []
        except Exception as e:
            print(f"Exception: {str(e)} - An error occurred while processing account details.")
            return []

        return operations

    ###############################
    #       CONTACT METHODS       #
    ###############################

    @is_allowable(model_name="CRMContact")
    def get_all_crm_contacts(self) -> list[Contact]:
        """Get all contacts in the client's CRM

        Returns:
            list[Contact]: List of Contacts
        """
        contacts = self.client.crm.contacts.list(
            expand=ContactsListRequestExpand.ACCOUNT,
        ).results
        return contacts

    @is_allowable(model_name="CRMContact")
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

    @is_allowable(model_name="CRMContact")
    def find_contact_by_email_address(self, email: str) -> Optional[Contact]:
        """Find contact by email address

        Args:
            email (str): Email address

        Returns:
            Optional[Contact]: Contact object
        """
        # Find Contact
        try:
            results = self.client.crm.contacts.list(
                email_addresses=email,
            ).results
            contact = results[0] if results else None
        except:  # API returns 404 if contact is not found
            return None

        return contact

    @is_allowable(model_name="CRMContact")
    def create_contact(self, prospect_id: int) -> tuple[Optional[str], str]:
        """Creates a contact in the client's CRM using a prospect ID

        Args:
            prospect_id (int): Prospect ID

        Returns:
            tuple[Optional[str], str]: Contact ID and message
        """
        # Get Prospect
        p: Prospect = Prospect.query.get(prospect_id)

        # Get Client SDR
        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        # Check for existing Contact
        if p.merge_contact_id:
            contact = self.find_contact_by_prospect_id(prospect_id)
            if contact:
                return contact.id, "Contact already created for this Prospect."
            else:
                p.merge_contact_id = None
                db.session.add(p)
                db.session.commit()

        # If Account is not created, create Account
        if not p.merge_account_id:
            account_id, message = self.create_account(prospect_id)
            if not account_id:
                return None, f"Could not create Account: {message}"

        print(f"⚡️ Creating contact for {p.first_name} {p.last_name} (#{p.id})")

        # Check for duplicates
        contact: Contact = self.find_contact_by_email_address(p.email)
        if contact:
            p.merge_contact_id = contact.id
            db.session.add(p)
            db.session.commit()
            return contact.id, "Contact already exists in CRM, linked to this prospect."

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

    @is_allowable(model_name="CRMAccount")
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

    @is_allowable(model_name="CRMAccount")
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

    @is_allowable(model_name="CRMAccount")
    def create_account(self, prospect_id: int) -> tuple[Optional[str], str]:
        """Create Account in the client's CRM

        Args:
            prospect_id (int): Prospect ID

        Returns:
            tuple[Optional[str], str]: Account ID and message
        """
        p: Prospect = Prospect.query.get(prospect_id)

        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        # Check for existing Account
        if p.merge_account_id:
            account = self.find_account_by_prospect_id(prospect_id)
            if account:
                return account.id, "Account already exists for this Prospect."
            else:
                p.merge_account_id = None
                db.session.add(p)
                db.session.commit()

        # If we do not have a company ID, try to find the company
        if not p.company_id:
            from src.company.services import find_company_for_prospect

            find_company_for_prospect(prospect_id=prospect_id)
            p = Prospect.query.get(prospect_id)

        print("⚡️ Creating account for company: ", p.company)

        # Check for duplicates (raw company name)
        account: Account = self.find_account_by_name(p.company)
        if account:
            p.merge_account_id = account.id
            db.session.add(p)
            db.session.commit()
            return account.id, "Account already exists in CRM, linked to this prospect."

        # Check for duplicates ([SellScale] prepended)
        account: Account = self.find_account_by_name("[SellScale] " + p.company)
        if account:
            p.merge_account_id = account.id
            db.session.add(p)
            db.session.commit()
            return account.id, "Account already exists in CRM, linked to this prospect."

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

    @is_allowable(model_name="Opportunity")
    def find_opportunity_by_prospect_id(
        self, prospect_id: int
    ) -> Optional[Opportunity]:
        """Find Opportunity by Prospect ID

        Args:
            prospect_id (int): Prospect ID

        Returns:
            Optional[Opportunity]: Opportunity object
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

    @is_allowable(model_name="Opportunity")
    def find_opportunity_by_opportunity_id(
        self, opportunity_id: str
    ) -> Optional[Opportunity]:
        """Find Opportunity by Opportunity ID

        Args:
            opportunity_id (str): Opportunity ID

        Returns:
            Optional[Opportunity]: Opportunity object
        """
        # Find Opportunity
        try:
            opportunity = self.client.crm.opportunities.retrieve(id=opportunity_id)
        except:
            return None

        return opportunity

    @is_allowable(model_name="Opportunity")
    def create_opportunity(
        self, prospect_id: int, stage_id_override: Optional[str] = None
    ) -> tuple[Optional[str], str]:
        """Create Opportunity in the client's CRM

        Args:
            prospect_id (int): Prospect ID
            stage_id_override (Optional[str]): Stage ID override

        Returns:
            tuple[Optional[str], str]: Opportunity ID and message
        """
        p: Prospect = Prospect.query.get(prospect_id)

        client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
            client_id=p.client_id
        ).first()
        if not client_sync_crm:
            return None, "CRM Sync not found."
        if not client_sync_crm.status_mapping:
            return None, "CRM Sync status mapping not found."

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
                p.merge_opportunity_id = None
                db.session.add(p)
                db.session.commit()

        stage_mapping = client_sync_crm.status_mapping
        status = stage_mapping.get(p.overall_status.value)
        if not status:
            # We select a random status if the status is not found
            status = stage_mapping[next(iter(stage_mapping))]
        if stage_id_override:
            status = stage_id_override

        # Get Opportunity Value TODO: Check the Campaign's contract size
        client: Client = Client.query.get(p.client_id)
        opportunity_value = client.contract_size or 500

        # Create Opportunity
        print(f"⚡️ Creating opportunity for {p.full_name} (#{p.id})")
        try:
            opportunity_res: OpportunityResponse = self.client.crm.opportunities.create(
                model=OpportunityRequest(
                    name=f"[SellScale] {p.company} ({p.full_name})",
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
                    # contact=p.merge_contact_id,
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

            # Create Note
            try:
                self.create_note.delay(prospect_id)
            except:
                pass

            return opportunity.id, "Opportunity created."
        except Exception as e:
            return None, str(e)

    ###############################
    #       LEADS METHODS         #
    ###############################

    @is_allowable(model_name="Lead")
    def find_lead_by_prospect_id(self, prospect_id: int) -> Optional[Lead]:
        """Find Lead by Prospect ID

        Args:
            prospect_id (int): Prospect ID

        Returns:
            Optional[Lead]: Lead object
        """
        prospect: Prospect = Prospect.query.get(prospect_id)
        merge_lead_id: str = prospect.merge_lead_id
        if not merge_lead_id:
            return None

        # Find Lead
        try:
            lead = self.client.crm.leads.retrieve(id=merge_lead_id)
        except:
            return None

        return lead

    @is_allowable(model_name="Lead")
    def find_lead_by_email_address(self, email_address: str) -> Optional[Lead]:
        """Find Lead by email address

        Args:
            email_address (str): Email address

        Returns:
            Optional[Lead]: Lead object
        """
        # Find Lead
        try:
            leads: PaginatedLeadList = self.client.crm.leads.list(
                email_addresses=email_address,
            )
            lead = leads.results[0] if leads.results else None
        except:
            return None

        return lead

    @is_allowable(model_name="Lead")
    def create_lead(self, prospect_id: int) -> tuple[Optional[str], str]:
        """Create Lead in the client's CRM

        Args:
            prospect_id (int): Prospect ID

        Returns:
            tuple[Optional[str], str]: Lead ID and message
        """
        p: Prospect = Prospect.query.get(prospect_id)

        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        # Check for existing Lead
        if p.merge_lead_id:
            lead = self.find_lead_by_prospect_id(prospect_id)
            if lead:
                return lead.id, "Lead already exists."
            else:
                p.merge_lead_id = None
                db.session.add(p)
                db.session.commit()

        print(f"⚡️ Creating lead for {p.full_name} (#{p.id})")

        # Check for duplicates
        lead: Lead = self.find_lead_by_email_address(p.email)
        if lead:
            p.merge_lead_id = lead.id
            db.session.add(p)
            db.session.commit()
            return lead.id, "Lead already exists in CRM, linked to this prospect."

        # Create Lead
        try:
            lead_res: LeadResponse = self.client.crm.leads.create(
                model=LeadRequest(
                    lead_source="SellScale",
                    title=p.title,
                    company=p.company,
                    first_name=p.first_name,
                    last_name=p.last_name,
                    addresses=[],
                    email_addresses=[EmailAddressRequest(email_address=p.email)],
                    phone_numbers=[],
                    owner=merge_user_id,
                )
            )
            lead: Lead = lead_res.model
            p.merge_lead_id = lead.id
            db.session.add(p)
            db.session.commit()

            return lead.id, "Lead created."
        except:
            return None, "Failed to create lead."

    ###############################
    #     ENGAGEMENT METHODS      #
    ###############################

    # WE ARE CHOOSING TO NOT USE ENGAGEMENTS AT THE MOMENT AS IT IS STILL IN BETA
    @is_allowable(model_name="Engagement")
    def create_engagement(self) -> tuple[Optional[str], str]:
        pass

    ###############################
    #         NOTE METHODS        #
    ###############################

    @is_allowable(model_name="Note")
    @celery.task
    def create_note(self, prospect_id: int):
        """Create Note in the client's CRM

        Args:
            prospect_id (int): Prospect ID

        Returns:
            tuple[Optional[str], str]: Note ID and message
        """
        p: Prospect = Prospect.query.get(prospect_id)

        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        archetype: ClientArchetype = ClientArchetype.query.get(p.archetype_id)
        merge_user_id = client_sdr.merge_user_id

        # Check for existing Note
        if p.merge_note_id:
            note = self.client.crm.notes.retrieve(id=p.merge_note_id)
            if note:
                return note.id, "Note already exists."
            else:
                p.merge_note_id = None
                db.session.add(p)
                db.session.commit()

        # Get the base content
        content = f"""<strong>[SellScale] Activity Breakdown for {p.full_name}</strong><br/><br/><strong>Campaign:</strong> {archetype.archetype}<br/><strong>Title:</strong> {p.colloquialized_title}<br/><strong>ICP Fit Reason:</strong> {p.icp_fit_reason}<br/><strong>Bio:</strong> {p.linkedin_bio}<br/><br/><strong>=== TIMELINE ===</strong><br/>"""

        # Add the prospect's overall history to the content
        overall_history = get_prospect_overall_history(p.id)
        subject_line_used = False
        for event in overall_history:
            author = event.get("author")
            message = event.get("message")
            subject = event.get("subject")
            email_body = event.get("email_body")
            engagement = event.get("engagement")
            date = event.get("date")
            formatted_date = date.strftime("%Y-%m-%d")
            if event.get("type") == "EMAIL":
                subject = f"Subject: {subject}</br>" if not subject_line_used else ""
                subject_line_used = True
                if (
                    engagement
                ):  # Engagement type for, say, "LINK CLICKED" or "EMAIL_OPENED"
                    content += (
                        f"<br/>{formatted_date} - <strong>{engagement}</strong><br/>"
                    )
                else:
                    content += f"<br/>{formatted_date} - <strong>{author} (Email)</strong><br/>{subject}{email_body}<br/>"
            elif event.get("type") == "LINKEDIN":
                content += f"<br/>{formatted_date} - <strong>{author} (LinkedIn)</strong><br/>{message}<br/>"
            elif event.get("type") == "STATUS_CHANGE":
                content += (
                    f"<br/>{author} {formatted_date} - <strong>{message}</strong><br/>"
                )

        try:
            # Assemble the kwargs, because not all IDs may be present
            kwargs = {
                "content": content,
                "owner": merge_user_id,
            }
            if p.merge_contact_id:
                kwargs.update({"contact": p.merge_contact_id})
            if p.merge_account_id:
                kwargs.update({"account": p.merge_account_id})
            if p.merge_opportunity_id:
                kwargs.update({"opportunity": p.merge_opportunity_id})

            note_res: NoteResponse = self.client.crm.notes.create(
                model=NoteRequest(**kwargs)
            )
            note: Note = note_res.model
            p.merge_note_id = note.id
            db.session.commit()

            return note, "Note created."
        except Exception as e:
            return None, str(e)
