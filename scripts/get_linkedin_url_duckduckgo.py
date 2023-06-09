#!/usr/bin/env python

import re
import sys
import urllib.parse
import requests
from duckduckgo_search import ddg
args = sys.argv

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Mobile Safari/537.36 Chrome-Lighthouse',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'en-US,en;q=0.5',
    'cache-control': 'no-cache',
    'cookie': 'ay=b; aq=-1; ax=v373-2b',
    'pragma': 'no-cache',
    'sec-ch-ua': '"Chromium";v="112", "Brave";v="112", "Not:A-Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'sec-gpc': '1',
    'upgrade-insecure-requests': '1',
}

name = args[1]
email = args[2]
region = 'us-en' # or 'uk-en' for Monday.com?

query = f'{name}, {email}, linkedin'

results = ddg(query, region=region, page=1, max_results=10)

match = re.search(r'linkedin\.com\/in\/([^"\'>]+)', str(results))

print(results)

#result = requests.get(f'https://duckduckgo.com/?q={urllib.parse.quote(query)}', headers=headers)

if match:
    print(match.group(0))
else:
    print('None found.')

# Before each run: time.sleep(random.uniform(1, 5))