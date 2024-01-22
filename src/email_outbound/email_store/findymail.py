import os
import requests

FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY")


class FindyMail:
    def __init__(self):
        self.api_key = FINDYMAIL_API_KEY

    def find_from_name_and_company(self, name: str, company: str) -> list:
        url = "https://app.findymail.com/api/search/name"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        params = {"name": name, "domain": company}
        response = requests.post(url, headers=headers, params=params)
        return response.json()
