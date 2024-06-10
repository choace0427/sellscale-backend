import os
from typing import Optional
import requests

from src.client.models import Client, ClientSDR
from src.pylon.pylon_types import AccountData, Issue, Organization, User


PYLON_API_KEY = os.environ.get("PYLON_API_KEY")


class Pylon:
    def __init__(self, client_sdr_id: int):
        self.bearer_token = PYLON_API_KEY
        self.client_sdr_id = client_sdr_id
        self.account_id = None
        self.requester_email = None
        self.requester_name = None

        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Set the requester email and name
        self.requester_email = client_sdr.email
        self.requester_name = client_sdr.name

        # Try to find the account ID based on the domain
        domain = client.domain
        accounts = self.get_accounts()
        for account in accounts:
            if account["domain"] and account["domain"] in domain:
                self.account_id = account["id"]
                break

    def get_active_organization(self) -> Organization:
        """Get the active organization for the user

        Returns:
            Organization: The active organization for the user
        """
        url = "https://api.usepylon.com/me"

        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()

        organization: Organization = response.json().get("data")

        return organization

    def get_accounts(self) -> list[AccountData]:
        """Get the accounts for the active organization

        Returns:
            AccountData: The accounts for the active organization
        """
        url = "https://api.usepylon.com/accounts"

        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()

        accounts: list[AccountData] = response.json().get("data")

        return accounts

    def get_users(self) -> list[User]:
        """Get the users for the active organization

        Returns:
            User: The users for the active organization
        """
        url = "https://api.usepylon.com/users"

        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()

        users: list[User] = response.json().get("data")

        return users

    def create_issue(
        self,
        title: str,
        body_html: str,
        account_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        requester_email: Optional[str] = None,
        requester_name: Optional[str] = None,
        assignee_id: Optional[str] = None,
        priority: Optional[str] = None,
        custom_fields: Optional[dict] = None,
        destination_metdata: Optional[dict] = None,
    ) -> Issue:
        """Create an issue

        Args:
            account_id (Optional[str]): The account ID to create the issue for. Defaults to None.

        Returns:
            Issue: The created issue
        """

        def get_default_account():
            return "96534a8a-66c0-4c68-9ac5-652cd011751e"

        url = "https://api.usepylon.com/issues"

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "title": title,
            "body_html": body_html,
            "account_id": account_id or self.account_id or get_default_account(),
            "requester_id": requester_id,
            "requester_email": requester_email or self.requester_email,
            "requester_name": requester_name or self.requester_name,
            "assignee_id": assignee_id,
            "priority": priority,
            "custom_fields": custom_fields,
            "destination_metadata": destination_metdata,
        }

        response = requests.request("POST", url, headers=headers, json=payload)
        response.raise_for_status()

        issue: Issue = response.json().get("data")

        return issue
