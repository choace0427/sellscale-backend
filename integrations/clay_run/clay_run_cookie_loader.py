import json
import re
from typing import Any, Dict, List, NewType, Optional, Union

PathSpec = NewType('PathSpec', List[Union[str, int]])


def str_path_to_path_steps(path: str, *delimiters: str) -> PathSpec:
    steps = re.split('|'.join(map(re.escape, delimiters)), path)
    for step in steps:
        if step.isdigit():
            yield int(step)
        else:
            yield step

def deep_get(obj: Union[List, Dict], path: str, default=None) -> Optional[Any]:
    steps = str_path_to_path_steps(path, '.')

    for step in steps:
        if not obj:
            return default

        if isinstance(obj, dict):
            obj = obj.get(step, None)
        elif isinstance(obj, list) and str(step).isnumeric():
            obj = obj[int(step)]
        else:
            try:
                obj = getattr(obj, step)
            except:
                return default

    return obj

har = json.load(open('sellscale-api/integrations/clay_run/clay_har.json'))

headers = deep_get(har, 'log.entries.14.request.cookies')
cookie_value = next(filter(lambda x: x['name'] == 'claysession', headers))['value']

open('bags/clay_cookie.txt', 'w+').write(cookie_value)
