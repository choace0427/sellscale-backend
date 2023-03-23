import requests
import os
from model_import import (
    Client,
    Prospect,
    VesselSequences,
    VesselMailboxes,
    ProspectEmail,
    GeneratedMessage,
    ProspectEmailStatus,
    VesselAPICachedResponses,
)
from typing import Optional
from app import db, celery
from tqdm import tqdm
from src.email_outbound.services import get_approved_prospect_email_by_id
from datetime import datetime, timedelta
from src.utils.abstract.type_checks import is_number

VESSEL_API_KEY = os.environ.get("VESSEL_API_KEY")


class SalesEngagementIntegration:
    """
    This class is used to interact with the Vessel Sales Engagement API
    """

    def __init__(self, client_id):
        if not is_number(client_id):
            raise ValueError("No client_id found")
        client: Client = Client.query.get(client_id)
        if not client:
            raise ValueError("Invalid client_id")
        if not client.vessel_access_token:
            raise ValueError("No Vessel access token found for client")
        self.client_id = client_id
        self.personalization_field_name = client.vessel_personalization_field_name
        self.vessel_api_key = VESSEL_API_KEY
        self.vessel_access_token = client.vessel_access_token
        self.vessel_api_url = "https://api.vessel.land"
        self.headers = {
            "vessel-api-token": VESSEL_API_KEY,
            "x-access-token": self.vessel_access_token,
        }

        if not self.personalization_field_name:
            raise ValueError(
                "No personalization field name found for client. Please add it to the client record."
            )
        if not self.vessel_api_key:
            raise ValueError(
                "No Vessel API key found. Please add it to the environment."
            )
        if not self.vessel_access_token:
            raise ValueError(
                "No Vessel access token found. Please add it to the client record."
            )

    def get_user_by_email(self, email):
        """
        Get a Sales Engagement user by email
        """
        nextPageCursor = None
        while nextPageCursor == None or nextPageCursor:
            url = f"{self.vessel_api_url}/engagement/users?accessToken={self.vessel_access_token}&cursor={nextPageCursor}&limit=100"
            response = requests.get(url, headers=self.headers)
            nextPageCursor = response.json()["nextPageCursor"]
            for user in response.json()["users"]:
                if user["email"] == email:
                    return user
            if not nextPageCursor:
                break

        return None

    def formatted_additional_field(self, personalization_dict):
        if self.client_id == 8:  # only for Curative / Salesloft users
            return {"custom_fields": personalization_dict}

        if self.client_id == 9:  # only for AdQuick / Outreach users
            return {"attributes": personalization_dict}

    def create_contact(self, first_name, last_name, job_title, emails, additional={}):
        """
        Create a Sales Engagement contact
        """
        url = f"{self.vessel_api_url}/engagement/contact"
        response = requests.post(
            url,
            headers=self.headers,
            json={
                "contact": {
                    "firstName": first_name,
                    "lastName": last_name,
                    "jobTitle": job_title,
                    "emails": [
                        {
                            "address": email,
                        }
                        for email in emails
                    ],
                    "additional": self.formatted_additional_field(additional),
                },
                "accessToken": self.vessel_access_token,
            },
        )
        return response.json()

    def search_contact_by_email(self, email):
        """
        Search for a Sales Engagement contact by email
        """
        url = f"{self.vessel_api_url}/engagement/contacts/search"
        response = requests.post(
            url,
            headers=self.headers,
            json={
                "accessToken": self.vessel_access_token,
                "filters": {"emails": {"address": {"equals": email}}},
            },
        )
        resp = response.json()
        if "contacts" not in resp or len(resp["contacts"]) == 0:
            return None
        return resp["contacts"][0]

    def create_or_update_contact_by_prospect_id(
        self,
        prospect_id,
    ):
        """
        Create or update a Sales Engagement contact by prospect_id
        """
        personalization_field_name = self.personalization_field_name
        prospect: Prospect = Prospect.query.get(prospect_id)
        approved_prospect_email_id: int = prospect.approved_prospect_email_id
        if not approved_prospect_email_id:
            raise ValueError("No approved prospect email found")
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            approved_prospect_email_id
        )
        personalized_first_line = prospect_email.personalized_first_line
        generated_message: GeneratedMessage = GeneratedMessage.query.filter_by(
            id=personalized_first_line
        ).first()
        personalized_message = generated_message.completion

        if not prospect:
            raise ValueError("Invalid prospect_id")
        if not personalized_message:
            raise ValueError("Personalized message is required")
        contact = self.search_contact_by_email(prospect.email)

        if not contact or "id" not in contact:
            contact = self.create_contact(
                prospect.first_name,
                prospect.last_name,
                prospect.title,
                [prospect.email],
                {personalization_field_name: personalized_message},
            )
        else:
            contact_id = contact["id"]
            contact = self.update_sellscale_personalization(
                contact_id, personalized_message
            )
        prospect.vessel_contact_id = contact["id"]
        db.session.add(prospect)
        db.session.commit()
        return contact

    def update_sellscale_personalization(self, contact_id, personalization):
        """
        Update the personalization_field_name field for a contact
        """
        personalization_field_name = self.personalization_field_name
        url = f"{self.vessel_api_url}/engagement/contact"
        response = requests.patch(
            url,
            headers=self.headers,
            json={
                "accessToken": self.vessel_access_token,
                "id": contact_id,
                "contact": {
                    "additional": self.formatted_additional_field(
                        {personalization_field_name: personalization}
                    )
                },
            },
        )
        return response.json()

    def find_mailbox_autofill_by_email(self, email):
        """
        Find a Sales Engagement mailbox by email using the cache
        """
        mailbox_options = (
            VesselMailboxes.query.filter(
                VesselMailboxes.email.ilike("%" + email + "%"),
                VesselMailboxes.access_token == self.vessel_access_token,
            )
            .limit(5)
            .all()
        )
        return [
            {"mailbox_id": mailbox.mailbox_id, "email": mailbox.email}
            for mailbox in mailbox_options
        ]

    def find_sequence_autofill_by_name(self, name):
        """
        Find a Sales Engagement sequence by name using the cache
        """
        sequence_options = (
            VesselSequences.query.filter(
                VesselSequences.name.ilike("%" + name + "%"),
                VesselSequences.access_token == self.vessel_access_token,
            )
            .limit(5)
            .all()
        )
        return [
            {"sequence_id": sequence.sequence_id, "name": sequence.name}
            for sequence in sequence_options
        ]

    def sync_data(self):
        """
        Sync data from Vessel
        """
        self.clear_mailbox_and_sequence_data()

        self.sync_sequence_data()
        self.sync_mailbox_data()
        print("Sync complete!")

    def clear_mailbox_and_sequence_data(self):
        """
        Clear mailbox data from cache
        """
        print("Clearing mailbox data...")
        VesselMailboxes.query.filter_by(access_token=self.vessel_access_token).delete()
        db.session.commit()
        print("Clearing sequence data...")
        VesselSequences.query.filter_by(access_token=self.vessel_access_token).delete()
        db.session.commit()
        print("Data cleared!\n")

    def sync_mailbox_data(self):
        """
        Find a Sales Engagement mailbox by email
        """
        print("Syncing mailbox data...")
        url = f"{self.vessel_api_url}/engagement/mailboxes"
        nextPageCursor = None
        while nextPageCursor == None or nextPageCursor:
            response = requests.get(
                url,
                headers=self.headers,
                params={
                    "accessToken": self.vessel_access_token,
                    "limit": 100,
                    "cursor": nextPageCursor,
                },
            )
            nextPageCursor = response.json()["nextPageCursor"]

            unadded_mailboxes = []
            for mailbox in response.json()["mailboxes"]:
                vessel_mailbox: VesselMailboxes = VesselMailboxes(
                    mailbox_id=mailbox["id"],
                    email=mailbox["email"],
                    access_token=self.vessel_access_token,
                )
                unadded_mailboxes.append(vessel_mailbox)
            db.session.bulk_save_objects(unadded_mailboxes)
            db.session.commit()

            if not nextPageCursor:
                break

    def sync_sequence_data(self):
        """
        Search for a Sales Engagement sequence by name
        """
        print("Syncing sequence data...")
        nextPageCursor = None
        url = f"{self.vessel_api_url}/engagement/sequences"
        while nextPageCursor == None or nextPageCursor:
            response = requests.get(
                url,
                headers=self.headers,
                params={
                    "accessToken": self.vessel_access_token,
                    "limit": 100,
                    "cursor": nextPageCursor,
                },
            )
            nextPageCursor = response.json()["nextPageCursor"]

            unadded_sequences = []
            for sequence in response.json()["sequences"]:
                vessel_sequence: VesselSequences = VesselSequences(
                    sequence_id=sequence["id"],
                    name=sequence["name"],
                    access_token=self.vessel_access_token,
                )
                unadded_sequences.append(vessel_sequence)
            db.session.bulk_save_objects(unadded_sequences)
            db.session.commit()

            if not nextPageCursor:
                break

    def add_contact_to_sequence(
        self, mailbox_id, sequence_id, contact_id, prospect_id: Optional[int] = None
    ):
        """
        Add a contact to a Sales Engagement sequence
        """
        url = f"{self.vessel_api_url}/engagement/sequence/start"
        response = requests.post(
            url,
            headers=self.headers,
            json={
                "accessToken": self.vessel_access_token,
                "id": sequence_id,
                "fields": {"mailboxId": mailbox_id, "contactId": contact_id},
            },
        )
        resp = response.json()
        sequence_id = resp.get("id")
        prospect_email = get_approved_prospect_email_by_id(prospect_id=prospect_id)
        if prospect_email:
            if sequence_id:
                prospect_email.vessel_sequence_id = sequence_id
                prospect_email.email_status = ProspectEmailStatus.SENT
            prospect_email.vessel_sequence_payload_str = str(resp)
            db.session.add(prospect_email)
            db.session.commit()

    def get_emails_for_contact(
        self, contact_id, sequence_id=None, do_not_hit_api: bool = False
    ):
        """
        Get all emails for a Sales Engagement contact
        """
        cached_resp = find_vessel_cached_response(
            self.vessel_access_token, str(contact_id), str(sequence_id)
        )        
        if cached_resp:
            return cached_resp
        if do_not_hit_api:
            return []
        url = f"{self.vessel_api_url}/engagement/emails/search"
        response = requests.post(
            url,
            headers=self.headers,
            json={
                "accessToken": self.vessel_access_token,
                "filters": {
                    "contactId": {"equals": str(contact_id)},
                    "sequenceId": {"equals": str(sequence_id)} if sequence_id else None,
                },
            },
        )
        if "emails" in response.json():
            resp = response.json()["emails"]
            create_vessel_cached_response(
                vessel_access_token=self.vessel_access_token,
                contact_id=str(contact_id),
                sequence_id=str(sequence_id),
                response_json=resp,
            )
            return resp
        else:
            return []

    def get_email_by_id(self, email_id):
        """
        Get a Sales Engagement email by id
        """
        url = f"{self.vessel_api_url}/engagement/email"
        response = requests.get(
            url,
            headers=self.headers,
            params={
                "accessToken": self.vessel_access_token,
                "id": email_id,
                "allFields": "true",
            },
        )
        return response.json()

    def sync_unsynced_prospects_vessel_contact_ids(self):
        prospects: list = Prospect.query.filter(
            Prospect.vessel_contact_id == None,
            Prospect.client_id == self.client_id,
        ).all()
        for prospect in tqdm(prospects):
            if not prospect.vessel_contact_id:
                sync_sales_engagement_contact_id_to_prospect.delay(
                    self.client_id, prospect.id
                )


@celery.task
def sync_sales_engagement_contact_id_to_prospect(client_id: int, prospect_id: int):
    """
    Sync the Sales Engagement contact id for a prospect
    """
    sei = SalesEngagementIntegration(client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    email = prospect.email
    if email:
        contact = sei.search_contact_by_email(email) or {}
        if contact.get("id"):
            contact_id = contact["id"]
            prospect.vessel_contact_id = contact_id
            db.session.add(prospect)
            db.session.commit()


def create_vessel_cached_response(
    vessel_access_token: str,
    contact_id: Optional[str] = None,
    sequence_id: Optional[str] = None,
    response_json: object = {},
):
    existing_entry = find_vessel_cached_response(
        vessel_access_token=vessel_access_token,
        contact_id=contact_id,
        sequence_id=sequence_id,
    )
    if existing_entry:
        return

    resp: VesselAPICachedResponses = VesselAPICachedResponses(
        vessel_access_token=vessel_access_token,
        contact_id=contact_id,
        sequence_id=sequence_id,
        response_json=response_json,
    )
    db.session.add(resp)
    db.session.commit()


def find_vessel_cached_response(
    vessel_access_token: str,
    contact_id: Optional[str] = None,
    sequence_id: Optional[str] = None,
    cache_duration: int = 2,  # number of days to look back
):
    query = VesselAPICachedResponses.query
    if contact_id:
        query = query.filter(VesselAPICachedResponses.contact_id == contact_id)
    if sequence_id:
        query = query.filter(VesselAPICachedResponses.sequence_id == sequence_id)
    query = query.filter(
        VesselAPICachedResponses.created_at
        > datetime.now() - timedelta(days=cache_duration)
    )
    resp = query.first()
    if resp:
        return resp.response_json
    return None
