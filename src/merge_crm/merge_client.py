from typing import Optional
from app import db
import datetime
import os
from merge.client import Merge
from model_import import ClientSDR, Prospect, Client, Company, ProspectOverallStatus
from merge.resources.crm import (
    ContactsRetrieveRequestExpand,
    ContactRequest,
    EmailAddressRequest,
    AccountRequest,
    OpportunityRequest,
    PatchedOpportunityRequest,
)


class MergeClient:
    def __init__(self, client_sdr_id: int):
        self.api_key = os.environ.get("MERGE_API_KEY") or ""

        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client_id = client_sdr.client_id
        client: Client = Client.query.get(client_id)
        self.account_token = client.merge_crm_account_token
        self.client = Merge(api_key=self.api_key, account_token=self.account_token)

    def find_contact_by_prospect_id(self, prospect_id: int):
        try:
            prospect: Prospect = Prospect.query.get(prospect_id)
            merge_contact_id: str = prospect.merge_contact_id
            contact = self.client.crm.contacts.retrieve(id=merge_contact_id)

            return contact
        except:
            return None

    def find_contact_by_email_address(self, email: str):
        try:
            contact = self.client.crm.contacts.list(
                email_addresses=email,
            )
            return contact
        except:
            return None

    def create_contact(self, prospect_id: int) -> tuple[Optional[str], str]:
        p: Prospect = Prospect.query.get(prospect_id)
        print(
            "⚡️ Creating contact for prospect #",
            p.id,
            "(",
            p.first_name,
            p.last_name,
            ")",
        )

        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        # check for existing contact
        if p.merge_contact_id:
            contact = self.find_contact_by_prospect_id(prospect_id)
            if contact:
                return contact.id, "Contact already exists."
            else:
                return (
                    None,
                    "Contact not found - ID may be corrupted or prospect may be deleted.",
                )

        if not p.merge_account_id:
            account_id, _ = self.create_account(prospect_id)
            if not account_id:
                return None, "Account not found."

        try:
            contact_res = self.client.crm.contacts.create(
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

            p.merge_contact_id = contact_res.model.id
            db.session.add(p)
            db.session.commit()
        except:
            # Find contact by email address
            contact = self.find_contact_by_email_address(p.email)
            if contact and contact.results and len(contact.results) > 0:
                p.merge_contact_id = contact.results[0].id
                db.session.add(p)
                db.session.commit()
                return p.merge_contact_id, "Contact already exists."

        return contact_res.model.id, "Contact created."

    def find_account_by_prospect_id(self, prospect_id: int):
        try:
            prospect: Prospect = Prospect.query.get(prospect_id)
            merge_account_id: str = prospect.merge_account_id
            account = self.client.crm.accounts.retrieve(id=merge_account_id)

            return account
        except:
            return None

    def find_account_by_name(self, name: str):
        try:
            account = self.client.crm.accounts.list(
                name=name,
            )
            return account.results[0] if account.results else None
        except:
            return None

    def create_account(self, prospect_id: int) -> tuple[Optional[str], str]:
        p: Prospect = Prospect.query.get(prospect_id)
        print("⚡️ Creating account for company: ", p.company)

        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        return_account_id = None
        return_message = ""

        # check for existing account
        if p.merge_account_id:
            account = self.find_account_by_prospect_id(prospect_id)
            if account:
                return_account_id = account.id
                return_message = "Account already exists."
            else:
                return (
                    None,
                    "Account not found - ID may be corrupted or prospect may be deleted.",
                )

        company: Company = Company.query.get(p.company_id)
        description = ""
        website_url = ""
        company_size = 0

        if company:
            description: str = company.description
            website_url: str = p.company_url
            company_size = p.employee_count

        try:
            account_res = self.client.crm.accounts.create(
                model=AccountRequest(
                    name=p.company,
                    description="[Source: SellScale]\n" + description,
                    website=website_url,
                    number_of_employees=company_size,
                    last_activity_at=datetime.datetime.utcnow().isoformat(),
                    owner=merge_user_id,
                )
            )

            p.merge_account_id = account_res.model.id
            db.session.add(p)
            db.session.commit()

            return_account_id = account_res.model.id
            return_message = "Account created."
        except:
            return_account_id = None
            return_message = "Account already exists."

        return return_account_id, return_message

    def create_opportunity(self, prospect_id: int) -> tuple[Optional[str], str]:
        p: Prospect = Prospect.query.get(prospect_id)
        print("⚡️ Creating opportunity for prospect #", p.id)
        company: Company = Company.query.get(p.company_id)

        client_sdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
        merge_user_id = client_sdr.merge_user_id

        description = ""
        if company:
            description = company.description

        if not p.merge_contact_id:
            contact_id, _ = self.create_contact(prospect_id)
            if not contact_id:
                return None, "Contact not found."

        if not p.merge_account_id:
            account_id, _ = self.create_account(prospect_id)
            if not account_id:
                return None, "Account not found."

        if p.merge_opportunity_id:
            return None, "Opportunity already exists."

        # TODO(Aakash) - Add staging map here per client
        stage_mapping = {
            ProspectOverallStatus.ACTIVE_CONVO: "cf07e8fa-b5c2-4683-966e-4dc471963a32",
            ProspectOverallStatus.DEMO: "e927f7f3-3e66-43fd-b9a8-baf4f0ee4846",
        }
        status = stage_mapping.get(
            p.overall_status, "cf07e8fa-b5c2-4683-966e-4dc471963a32"
        )

        try:
            opportunity_res = self.client.crm.opportunities.create(
                model=OpportunityRequest(
                    name="[SellScale] " + p.company,
                    description="{first_name}, who is a {title} at {company}, is interested in our services.\n\nFit Reason:\n{fit_reason}\n\nDescription:\n{company_description}".format(
                        first_name=p.first_name,
                        title=p.title,
                        company=p.company,
                        fit_reason=p.icp_fit_reason,
                        company_description=description,
                    ),
                    amount=500,
                    last_activity_at=datetime.datetime.utcnow().isoformat(),
                    account=p.merge_account_id,
                    contact=p.merge_contact_id,
                    status="OPEN",
                    owner=merge_user_id,
                )
            )

            if opportunity_res.model.id:
                self.client.crm.opportunities.partial_update(
                    id=opportunity_res.model.id,
                    model=PatchedOpportunityRequest(stage=status),
                )

            p.merge_opportunity_id = opportunity_res.model.id
            db.session.add(p)
            db.session.commit()

            return opportunity_res.model.id, "Opportunity created."
        except Exception as e:
            return None, str(e)

    def get_stages(self) -> list:
        return self.client.crm.stages.list()

    def get_users(self) -> list:
        return self.client.crm.users.list()
