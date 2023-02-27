import requests
import os
from model_import import Client, Prospect
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

    def search_contact_by_prospect_id(self, prospect_id):
        """
        Search for a Sales Engagement contact by prospect_id
        """
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            raise ValueError("Invalid prospect_id")
        contact = self.search_contact_by_email(prospect.email)
        if not contact:
            return None
        contact_id = contact["id"]
        prospect.vessel_contact_id = contact_id
        db.session.add(prospect)
        db.session.commit()
        return contact

    def update_sellscale_personalization(self, contact_id, personalization):
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
                        "custom_fields": {"SellScale_Personalization": personalization}
                    }
                },
            },
        )
        return response.json()

    def find_mailbox_by_email(self, email):
        """
        Find a Sales Engagement mailbox by email
        """
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
            for mailbox in response.json()["mailboxes"]:
                if mailbox["email"] == email:
                    return mailbox

    def search_sequences_by_name(self, name):
        """
        Search for a Sales Engagement sequence by name
        """
        nextPageCursor = 1
        url = f"{self.vessel_api_url}/engagement/sequences"
        sequences = []
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
            for sequence in response.json()["sequences"]:
                if name.lower() in sequence["name"].lower():
                    sequences.append(sequence)
        return sequences

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
