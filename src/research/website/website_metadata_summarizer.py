"""
Generates a summary of the metadata for a website and returns it as a string.
Uses a caching mechanism to avoid making the same request multiple times.
"""

import requests
from bs4 import BeautifulSoup
import yaml
import sys
import openai
import os
from ctypes import Union
from typing import Optional
from src.ml.openai_wrappers import OPENAI_CHAT_GPT_4_MODEL, wrapped_chat_gpt_completion
from src.research.models import WebsiteMetadataCache
from app import db

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


# This is a placeholder function as direct interaction with GPT-4 is not possible in this context.
# In a real-world scenario, you would replace this with an API call or integration with GPT-4.
def gpt4_interpret_html(html_content: str):
    # Sample output, just for demonstration. You'll replace this with GPT-4 inference.
    completion = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": """Leverage this HTML content: 
{html_content}

----
INSTRUCTIONS:
Extract key details from the HTML content and return a JSON object with the following fields:
- description: (mandatory) a short description of the company. 2-3 sentences long. ex. 'We are a CRM company that uses AI to help small businesses manage their customers. ...
- summary: (mandatory) a one line tagline for the company ex. 'Supercharge your outbound with AI'
- products: (mandatory) a list of 3-4 main products offered by the company ex. 'CRM', 'ERP', 'HR'
- industries: (mandatory) a list of industries the company operates in ex. 'healthcare', 'finance', 'education'
- target_profiles: (mandatory) a list of target customer profiles for the company ex. 'small business owners', 'developers', 'hospital administrators'
- company type: (mandatory) the type of company. ex. 'B2B', 'B2C', 'B2B2C'
- location: (mandatory) the location the company targets. ex. 'United States', 'Canada', 'Global'
- highlights: (mandatory) list of any 2-3 notable facts about the company related to company-things like fundraises, recent news, etc. ex. 'raised $100M in Series A', 'recently acquired by Google'
- linkedin_url: the LinkedIn URL for the company ex. 'https://www.linkedin.com/company/acme'
- crunchbase_url: the Crunchbase URL for the company ex. 'https://www.crunchbase.com/organization/acme'
- twitter_url: the Twitter URL for the company ex. 'https://twitter.com/acme'
- instagram_url: the Instagram URL for the company ex. 'https://www.instagram.com/acme/'
- email: the email address for the company ex. 'johnny@acm.ecom'
- address: the address for the company ex. '123 Main St, San Francisco, CA 94105'
- company_name: the name of the company ex. 'Acme'
- mission: extrapolate the mission statement of the company ex. 'We help small businesses manage their customers'
- value_proposition: extrapolate the value proposition of the company ex. 'We help small businesses manage their customers'

Fill in all the fields above with the correct values. If a field is not applicable, leave it blank.

You must fill in all the mandatory fields.
----
JSON OUTPUT:""".format(
                    html_content=html_content
                ),
            }
        ],
        max_tokens=500,
        temperature=0.75,
        top_p=1.0,
        model=OPENAI_CHAT_GPT_4_MODEL,
    )
    return completion


def get_website_details(url: str) -> dict:
    # Get raw HTML content
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(
            f"Failed to fetch content from {url}. Status Code: {response.status_code}"
        )

    html_content = response.text

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    # get text
    clean_text = " ".join([text for text in soup.stripped_strings])
    # add all URLs found on website to text too
    for link in soup.find_all("a"):
        keywords_to_check = [
            "press",
            "jobs",
            "careers",
            "about",
            "contact",
            "team",
            "company",
            "blog",
            "twitter",
            "facebook",
            "instagram",
            "linkedin",
            "crunchbase",
        ]
        if link.get("href") is not None and any(
            keyword in link.get("href") for keyword in keywords_to_check
        ):
            clean_text = link.get("href") + " " + clean_text

    # max to 4000 chars
    clean_text = clean_text[:4000]

    # Use GPT-4 to interpret the HTML content
    gpt4_results = gpt4_interpret_html(clean_text)

    convert_to_json = yaml.safe_load(gpt4_results)

    # add 'website_url' field to JSON
    convert_to_json["website_url"] = url

    return convert_to_json


def get_website_details_from_cache(url: str) -> Optional[str]:
    # Check if we have a cached version of the website details
    cached_website_details = WebsiteMetadataCache.query.filter_by(
        website_url=url
    ).first()
    if cached_website_details:
        return cached_website_details.to_dict()

    return None


def cache_website_details(url: str, website_details: dict):
    # Cache the website details
    website_metadata_cache = WebsiteMetadataCache(
        website_url=url,
        description=website_details.get("description", ""),
        summary=website_details.get("summary", ""),
        products=website_details.get("products", []),
        industries=website_details.get("industries", []),
        target_profiles=website_details.get("target_profiles", []),
        company_type=website_details.get("company_type", ""),
        location=website_details.get("location", ""),
        highlights=website_details.get("highlights", []),
        linkedin_url=website_details.get("linkedin_url", ""),
        twitter_url=website_details.get("twitter_url", ""),
        crunchbase_url=website_details.get("crunchbase_url", ""),
        instagram_url=website_details.get("instagram_url", ""),
        email=website_details.get("email", ""),
        address=website_details.get("address", ""),
        company_name=website_details.get("company_name", ""),
        mission=website_details.get("mission", ""),
        value_proposition=website_details.get("value_proposition", ""),
    )
    db.session.add(website_metadata_cache)
    db.session.commit()


def process_cache_and_print_website(url: str):
    # Check if we have a cached version of the website details
    cached_website_details = get_website_details_from_cache(url)
    if cached_website_details:
        print(f"Found cached website details for {url}.")
        print(cached_website_details)
        return cached_website_details

    # If we don't have a cached version, fetch the website details
    website_details: dict = get_website_details(url)
    if not website_details:
        print(f"Failed to fetch website details for {url}.")
        return

    # Cache the website details
    cache_website_details(url, website_details)

    return website_details
