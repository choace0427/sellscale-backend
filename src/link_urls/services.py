from typing import Optional
import requests
import json
import os
from app import db
from src.link_urls.models import LinkURL
from model_import import ClientSDR


def add_url_link(client_sdr_id: Optional[int], long_url: str, description: str):

    url = "https://t.ly/api/v1/link/shorten"
    payload = {
        "long_url": long_url,
        "domain": None,
        "expire_at_datetime": None,
        "description": description,
        "public_stats": False,
        "tags": [],
        "pixels": [],
    }
    headers = {
        "Authorization": f"Bearer {os.environ.get('TLY_API_KEY')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.request("POST", url, headers=headers, json=payload)
    data = response.json()

    print(data)

    tiny_url = data.get("short_url")

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    url_link = LinkURL(
        client_id=sdr.client_id if sdr else None,
        url=long_url,
        tiny_url=tiny_url,
        description=description,
    )
    db.session.add(url_link)
    db.session.commit()

    return url_link.id, tiny_url


def get_url_stats(url_id: int):

    url_link: LinkURL = LinkURL.query.get(url_id)
    if not url_link:
        return None

    url = "https://t.ly/api/v1/link/stats"
    params = {
        "short_url": url_link.tiny_url,
    }
    headers = {
        "Authorization": f"Bearer {os.environ.get('TLY_API_KEY')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    response = requests.request("GET", url, headers=headers, params=params)
    return response.json()
