import requests
import os
from model_import import (
    Client,
    Prospect,
    VesselSequences,
    VesselMailboxes,
    ProspectEmail,
    GeneratedMessage,
)
from app import db

VESSEL_API_KEY = os.environ.get("VESSEL_API_KEY")


class SalesEngagementIntegration:
    """
    This class is used to interact with the Vessel Sales Engagement API
    """

    def __init__(self, client_id):
        client: Client = Client.query.get(client_id)
        if not client:
            raise ValueError("Invalid client_id")
        if not client.vessel_access_token:
            raise ValueError("No Vessel access token found for client")
        self.vessel_api_key = VESSEL_API_KEY
        self.vessel_access_token = client.vessel_access_token
        self.vessel_api_url = "https://api.vessel.land/"
        self.headers = {
            "vessel-api-token": VESSEL_API_KEY,
            "x-access-token": self.vessel_access_token,
        }

    def get_user_by_email(self, email):
        """
        Get a Sales Engagement user by email
        """
        nextPageCursor = 1
        while nextPageCursor:
            url = f"{self.vessel_api_url}/engagement/users?accessToken={self.vessel_access_token}&cursor={nextPageCursor}&limit=100"
            response = requests.get(url, headers=self.headers)
            nextPageCursor = response.json()["nextPageCursor"]
            for user in response.json()["users"]:
                if user["email"] == email:
                    return user
        return None

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
                    "additional": {"custom_fields": additional},
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
        if len(resp["contacts"]) == 0:
            return None
        return resp["contacts"][0]

    def create_or_update_contact_by_prospect_id(
        self,
        prospect_id,
        personalization_field_name="SellScale_Personalization",
    ):
        """
        Create or update a Sales Engagement contact by prospect_id
        """
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
        if not contact:
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
                contact_id, personalized_message, personalization_field_name
            )
        prospect.vessel_contact_id = contact["id"]
        db.session.add(prospect)
        db.session.commit()
        return contact

    def update_sellscale_personalization(
        self, contact_id, personalization, personalization_field_name
    ):
        """
        Update the SellScale_Personalization field for a contact
        """
        url = f"{self.vessel_api_url}/engagement/contact"
        response = requests.patch(
            url,
            headers=self.headers,
            json={
                "accessToken": self.vessel_access_token,
                "id": contact_id,
                "contact": {
                    "additional": {
                        "custom_fields": {personalization_field_name: personalization}
                    }
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
        nextPageCursor = 1
        while nextPageCursor:
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

    def sync_sequence_data(self):
        """
        Search for a Sales Engagement sequence by name
        """
        print("Syncing sequence data...")
        nextPageCursor = 1
        url = f"{self.vessel_api_url}/engagement/sequences"
        while nextPageCursor:
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

    def add_contact_to_sequence(self, mailbox_id, sequence_id, contact_id):
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
        return response.json()

    def get_emails_for_contact(self, contact_id, sequence_id):
        """
        Get all emails for a Sales Engagement contact
        """
        url = f"{self.vessel_api_url}/engagement/emails/search"
        response = requests.post(
            url,
            headers=self.headers,
            json={
                "accessToken": self.vessel_access_token,
                "filters": {
                    "contactId": {"equals": contact_id},
                    "sequenceId": {"equals": sequence_id},
                },
            },
        )
        return response.json()["emails"]

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
