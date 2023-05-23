
from typing import Union

import requests
from src.client.models import ClientSDR
from app import db


def update_calendly_access_token(client_sdr_id: int, code: Union[str, None] = None, refresh_token: Union[str, None] = None):
    
    if code:
        return update_calendly_access_token_via_code(client_sdr_id, code)
    
    if refresh_token:
        return update_calendly_access_token_via_refresh_token(client_sdr_id, refresh_token)
    
    return False


def update_calendly_access_token_via_code(client_sdr_id: int, code: str):
    
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    res = requests.post(
        url=f"https://auth.calendly.com/oauth/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        json={
            "grant_type": 'authorization_code',
            "code": code,
            "redirect_uri": "https://app.sellscale.com/authcalendly",
        },
    )
    if res.status_code != 200:
        return False

    result = res.json()

    sdr.calendly_access_token = result["access_token"]
    sdr.calendly_refresh_token = result["refresh_token"]
    db.session.commit()

    return True



def update_calendly_access_token_via_refresh_token(client_sdr_id: int, refresh_token: str):
    
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    res = requests.post(
        url=f"https://auth.calendly.com/oauth/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        json={
            "grant_type": 'refresh_token',
            "refresh_token": refresh_token,
        },
    )
    if res.status_code != 200:
        return False

    result = res.json()

    sdr.calendly_access_token = result["access_token"]
    sdr.calendly_refresh_token = result["refresh_token"]
    db.session.commit()

    return True
