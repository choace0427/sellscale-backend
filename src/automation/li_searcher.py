import os
import re
import urllib.parse
import requests
import time
import random

from src.utils.slack import URL_MAP, send_slack_message

serp_api_key = os.getenv("SERP_API_KEY")
headers = {"user-agent": "my-app/0.0.1"}


def search_for_li(timezone: str, email: str = "", name: str = "", company: str = "", title: str = "", use_email: bool = True):
    region = "uk-en" if timezone.startswith("Europe/") else "us-en"

    # name_parts = name.split(" ")
    # if len(name_parts) == 2:
    #     first = name_parts[0]
    #     middle = ""
    #     last = name_parts[1]
    # elif len(name_parts) == 3:
    #     first = name_parts[0]
    #     middle = name_parts[1]
    #     last = name_parts[2]
    # else:
    #     return None

    # print(f'Searching for "{query}"...')

    # Before each run, wait so we don't get rate limited
    # time.sleep(random.uniform(1, 5))
    

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

    def _internal_find_li(use_email: bool = True):
       
        query = ""
        if name:
            query += f"{name}, "
        if email and use_email:
            query += f"{email}, "
        if company:
            query += f"{company}, "
        if title:
            query += f"{title, }"
        query += "site:linkedin.com/in"

        serp_api_key = os.getenv("SERP_API_KEY")

        try:
            # Use Google SERP API - START
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
            
            # Use Google SERP API - END
        except Exception as e:
            if use_email:
                return _internal_find_li(use_email=False)
            else:
                send_slack_message(
                    message=f"🚨 Serp API is failing during uploading.\n{str(e)}\nPlease ensure there are sufficient credits by visiting https://serpapi.com/.",
                    webhook_urls=[URL_MAP["user-errors"]],
                )
                return None

    return _internal_find_li(use_email=use_email)
