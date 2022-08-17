import requests.auth
from requests.models import PreparedRequest


class ApiKeyParamAuthBase(requests.auth.AuthBase):
    def __init__(self, key_name: str, key_value: str) -> None:
        self._key_name = key_name
        self._key_value = key_value

    def __call__(self, r: PreparedRequest):
        r.prepare_url(r.url, {self._key_name: self._key_value})
        return r
