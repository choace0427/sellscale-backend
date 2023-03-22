import requests
import os

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY")


def get_email_from_hunter(company_website: str, first_name: str, last_name: str):
    url = "https://api.hunter.io/v2/email-finder?domain={domain}&first_name={first_name}&last_name={last_name}&api_key={api_key}".format(
        domain=company_website,
        first_name=first_name,
        last_name=last_name,
        api_key=HUNTER_API_KEY,
    )
    response = requests.get(url)
    if response.status_code != 200:
        return False, {"error": response.text}
    return True, {
        "email": response.json()["data"]["email"],
        "score": response.json()["data"]["score"],
    }
