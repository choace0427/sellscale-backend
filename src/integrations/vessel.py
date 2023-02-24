import requests


class SalesEngagementIntegration:
    """
    This class is used to interact with the Vessel Sales Engagement API
    """

    def __init__(self, vessel_api_key, vessel_access_token):
        self.vessel_api_key = vessel_api_key
        self.vessel_access_token = vessel_access_token
        self.vessel_api_url = "https://api.vessel.land/"
        self.headers = {
            "vessel-api-token": self.vessel_api_key,
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
                    "additional": additional,
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

    def update_sellscale_personalization(self, contact_id, personalization):
        """
        Update the SellScale_Personalization field for a contact
        """
        # todo(Aakash) investigate why this isn't working
        url = f"{self.vessel_api_url}/engagement/contact"
        response = requests.patch(
            url,
            headers=self.headers,
            json={
                "accessToken": self.vessel_access_token,
                "id": contact_id,
                "contact": {
                    "additional": {"SellScale_Personalization": personalization}
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
        print(response)
        return response.json()
