
import re
import urllib.parse
import requests
import time
import random

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

def search_for_li(email: str, timezone: str, name: str = '', company: str = ''):
    region = 'uk-en' if timezone.startswith('Europe/') else 'us-en'

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
        return None

    query = ''
    if name: query += f'{name}, '
    if email: query += f'{email}, '
    if company: query += f'{company}, '
    query += 'site:linkedin.com/in'

    #print(f'Searching for "{query}"...')

    # Before each run, wait so we don't get rate limited
    time.sleep(random.uniform(1, 5))

    from duckduckgo_search import ddg
    results = ddg(query, region=region, page=1, max_results=10)

    if not results: return None

    for result in results:
        #print(result.get('title'))
        #print(name)
        match = re.search(fr'^{first}\s*\w*\s+({last[0]}|{last}).\s*-.*$', result.get('title'))
        if match:
            #print('Matched!')
            return result.get('href')

    # Old system of hitting DuckDuckGo directly
    #print(f'https://duckduckgo.com/?q={urllib.parse.quote(query)}')
    #result = requests.get(f'https://duckduckgo.com/?q={urllib.parse.quote(query)}', headers=headers)
    #print(result.status_code)

    #print(result.text)

    return None

