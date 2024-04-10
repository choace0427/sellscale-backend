import requests
import json
import yaml
from src.research.linkedin.services import (
    ISCRAPER_API_KEY,
    LINKEDIN_SEARCH_URL,
    DATA_TYPES_URL,
    research_personal_profile_details,
)


def get_location_ids_from_iscraper(location: str):
    payload = json.dumps({"keyword": location, "dtype": "geos"})
    headers = {"X-API-KEY": ISCRAPER_API_KEY, "Content-Type": "application/json"}

    response = requests.request("POST", DATA_TYPES_URL, headers=headers, data=payload)

    d = yaml.safe_load(response.text)
    location_ids = [x["id"] for x in d]

    return location_ids


def get_linkedin_link_from_iscraper(name: str, location: str):
    location_ids = get_location_ids_from_iscraper(location)

    payload = json.dumps(
        {
            "keyword": name,
            "search_type": "people",
            "locations": location_ids,
            "per_page": 50,
            "offset": 0,
        }
    )
    headers = {"X-API-KEY": ISCRAPER_API_KEY, "Content-Type": "application/json"}

    response = requests.request(
        "POST", LINKEDIN_SEARCH_URL, headers=headers, data=payload
    )
    data = yaml.safe_load(response.text)

    if not data or not data["results"]:
        return {"message": "Prospect not found"}

    profile_id = data["results"][0]["universal_id"]
    return {"link": "https://www.linkedin.com/in/{}/".format(profile_id)}


def get_linkedin_search_results_from_iscraper(name: str, location: str):
    location_ids = get_location_ids_from_iscraper(location)

    payload = json.dumps(
        {
            "keyword": name,
            "search_type": "people",
            "locations": location_ids,
            "per_page": 50,
            "offset": 0,
        }
    )
    headers = {"X-API-KEY": ISCRAPER_API_KEY, "Content-Type": "application/json"}

    response = requests.request(
        "POST", LINKEDIN_SEARCH_URL, headers=headers, data=payload
    )
    data = yaml.safe_load(response.text)

    if not data or not data["results"]:
        return {"message": "Prospect not found"}

    profile_id = data["results"][0]["universal_id"]
    personal_data = research_personal_profile_details(profile_id=profile_id)

    return personal_data
