#!/usr/bin/env python

import sys
import requests

import json
import os
from pprint import pprint
import re

args = sys.argv

name = args[1]
email = args[2]
company = args[3]
region = 'en-US'

def _internal_find_li(use_email: bool = True):
       
    query = ""
    if name:
        query += f"{name}, "
    if email and use_email:
        query += f"{email}, "
    if company:
        query += f"{company}, "
    query += "site:linkedin.com/in"

    serp_api_key = os.getenv("SERP_API_KEY")

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
    except Exception as e:
        if use_email:
            return _internal_find_li(use_email=False)
        else:
            raise e
    

print(_internal_find_li())