#!/usr/bin/env python

import re
import sys
import urllib.parse
import requests
from duckduckgo_search import ddg
args = sys.argv

name = args[1]
email = args[2]
country_code = 'US' # https://api.search.brave.com/app/documentation/language-codes#country-codes

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

url = f"https://api.search.brave.com/res/v1/web/search?q={query}&country={country_code}&count=20"
headers = {
    "Accept": "application/json",
    "X-Subscription-Token": "BSAsa0_YTXGdXKBX3AUiwMB9NEug4ph"
}
response = requests.get(url, headers=headers)
data = response.json()

for result in data.get('web', {}).get('results', []):
    print(result.get('title'))
    match = re.search(fr'^{first}\s*\w*\s+({last[0]}|{last}).\s*-.*$', result.get('title'))
    if match:
        print(result.get('url'))

