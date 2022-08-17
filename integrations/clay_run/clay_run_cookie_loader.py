import json
from sellscale.utils.abstract.attr_utils import deep_get


har = json.load(open('sellscale/integrations/clay_run/clay_har.json'))

headers = deep_get(har, 'log.entries.14.request.cookies')
cookie_value = next(filter(lambda x: x['name'] == 'claysession', headers))['value']

open('bags/clay_cookie.txt', 'w+').write(cookie_value)
