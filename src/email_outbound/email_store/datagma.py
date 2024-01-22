import os
import requests

DATAGMA_API_KEY = os.environ.get("DATAGMA_API_KEY")


class DataGMA:
    def __init__(self):
        self.api_key = DATAGMA_API_KEY

    def find_from_name_and_company(self, name: str, company: str) -> list:
        url = f"https://gateway.datagma.net/api/ingress/v6/findEmail?apiId={self.api_key}&fullName={name}&company={company}"
        response = requests.get(url)
        return response.json()
