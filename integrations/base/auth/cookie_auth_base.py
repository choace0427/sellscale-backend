import requests.auth
from requests.models import PreparedRequest


class CookieValueAuthBase(requests.auth.AuthBase):
    def __init__(self, cookie_name: str, cookie_value: str) -> None:
        self._cookie_name = cookie_name
        self._cookie_value = cookie_value

    def __call__(self, r: PreparedRequest):
        old_cookie = ''
        if 'cookie' in r.headers:
            old_cookie = r.headers['cookie']

        r.headers['cookie'] = f'{old_cookie}; {self._cookie_name}={self._cookie_value}'
        return r
