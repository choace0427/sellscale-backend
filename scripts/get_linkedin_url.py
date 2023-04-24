#!/usr/bin/env python

import re
import sys
from duckduckgo_search import ddg
args = sys.argv

name = args[1]
email = args[2]
region = 'us-en' # or 'uk-en' for Monday.com?

query = f'{name}, {email}, linkedin'

results = ddg(query, region=region, time='y')

match = re.search(r'linkedin\.com\/in\/([^"\'>]+)', str(results))

if match:
    print(match.group(0))
else:
    print('None found.')

# Before each run: time.sleep(random.uniform(1, 5))
