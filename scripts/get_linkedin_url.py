#!/usr/bin/env python

import requests
import re
import sys
args = sys.argv

name = args[1]
email = args[2]

# Get DuckDuckGo search results
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
}

query = f'{name}, {email}, linkedin'
result = requests.get(f'https://duckduckgo.com/html?q={query}', headers=headers).text

match = re.search(r'linkedin\.com\/in\/([^">]+)', result)

if match:
    print(match.group(0))
else:
    print('None found.')