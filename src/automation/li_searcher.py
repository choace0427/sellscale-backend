import os
import re
import urllib.parse
import requests
import time
import random

from src.utils.slack import URL_MAP, send_slack_message

serp_api_key = os.getenv("SERP_API_KEY")
headers = {"user-agent": "my-app/0.0.1"}


def search_for_li(email: str, timezone: str, name: str = "", company: str = ""):
    region = "uk-en" if timezone.startswith("Europe/") else "us-en"

    name_parts = name.split(" ")
    if len(name_parts) == 2:
        first = name_parts[0]
        middle = ""
        last = name_parts[1]
    elif len(name_parts) == 3:
        first = name_parts[0]
        middle = name_parts[1]
        last = name_parts[2]
    else:
        return None

    query = ""
    if name:
        query += f"{name}, "
    if email:
        query += f"{email}, "
    if company:
        query += f"{company}, "
    query += "site:linkedin.com/in"

    # print(f'Searching for "{query}"...')

    # Before each run, wait so we don't get rate limited
    # time.sleep(random.uniform(1, 5))

    # Use Google SERP API - START
    try:
        from serpapi import GoogleSearch

        params = {
            "q": query,
            "location": "Austin, Texas, United States",
            "hl": "en",
            "gl": "us",
            "google_domain": "google.com",
            "api_key": serp_api_key,
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        potential_linkedin_link = results["organic_results"][0]["link"]
        if "linkedin.com" in potential_linkedin_link:
            return potential_linkedin_link
    except:
        send_slack_message(
            message="🚨 Serp API is failing during uploading. Please ensure there are sufficient credits by visiting https://serpapi.com/.",
            webhook_urls=[URL_MAP["user-errors"]],
        )
    # Use Google SERP API - END

    # Use the DuckDuckGo API - START
    # from duckduckgo_search import ddg

    # results = ddg(query, region=region, page=1, max_results=10)

    # if not results:
    #     return None

    # for result in results:
    #     # print(result.get('title'))
    #     # print(name)
    # match = re.search(
    #     rf"^{first}\s*\w*\s+({last[0]}|{last}).\s*\|.*$", result.get("title")
    # )
    # if match:
    #     return result.get("href")
    # Use the DuckDuckGo API - END

    # Old system of hitting DuckDuckGo directly
    # print(f'https://duckduckgo.com/?q={urllib.parse.quote(query)}')
    # result = requests.get(f'https://duckduckgo.com/?q={urllib.parse.quote(query)}', headers=headers)
    # print(result.status_code)

    # print(result.text)

    return None
