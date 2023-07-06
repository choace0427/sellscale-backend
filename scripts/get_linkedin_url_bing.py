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
region = 'en-US'

'''
Documentation: https://docs.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
'''

# Add your Bing Search V7 subscription key and endpoint to your environment variables.
subscription_key = os.environ['BING_SEARCH_SUBSCRIPTION_KEY']
endpoint = os.environ['BING_SEARCH_ENDPOINT']

# Query term(s) to search for. 
name_parts = name.split(' ')
if len(name_parts) == 2:
    first = name_parts[0]
    middle = ''
    last = name_parts[1]
elif len(name_parts) == 3:
    first = name_parts[0]
    middle = name_parts[1]
    last = name_parts[2]
else:
    first = ''
    middle = ''
    last = ''

query = ''
if name: query += f'"{first}" "{last}", '
if email: query += f'{email}, '
query += 'site:linkedin.com/in'

# Construct a request
params = { 'q': query, 'mkt': region }
headers = { 'Ocp-Apim-Subscription-Key': subscription_key }

# Call the API
try:
    response = requests.get(endpoint, headers=headers, params=params)
    response.raise_for_status()
    results = response.json()

    #pprint(results.get('webPages').get('value'))

    for result in results.get('webPages').get('value'):
      # print(result.get('name'))
      # print(name)
      match = re.search(
        rf"^{first}\s*\w*\s+({last[0] if len(last) > 0 else ''}|{last}).\s*\|.*$", result.get("name")
      )
      if match:
        # print('Matched!')
        print(result.get('url'))
        break


    #print('None found.')

except Exception as ex:
    raise ex