import json
from src.automation.models import PhantomBusterConfig, PhantomBusterType
from app import db
import requests
import os

PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY")
GET_PHANTOMBUSTER_AGENTS_URL = "https://api.phantombuster.com/api/v2/agents/fetch-all"


def create_phantom_buster_config(
    client_id: int,
    client_sdr_id: int,
    google_sheets_uuid: str,
    phantom_name: str,
    phantom_uuid: str,
):
    existing_config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id,
        PhantomBusterConfig.pb_type == PhantomBusterType.OUTBOUND_ENGINE,
    ).first()
    if existing_config:
        return {"phantom_buster_config_id": existing_config.id}

    pb_config = PhantomBusterConfig(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        google_sheets_uuid=google_sheets_uuid,
        phantom_name=phantom_name,
        phantom_uuid=phantom_uuid,
    )
    db.session.add(pb_config)
    db.session.commit()

    return {"phantom_buster_config_id": pb_config.id}


def get_all_phantom_busters():
    headers = {
        "accept": "application/json",
        "X-Phantombuster-Key": "UapzERoGG1Q7qcY1jmoisJgR6MNJUmdL2w4UcLCtOJQ",
    }

    response = requests.get(GET_PHANTOMBUSTER_AGENTS_URL, headers=headers)
    response_json = json.loads(response.text)

    phantom_map = []
    for x in response_json:
        config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
            PhantomBusterConfig.phantom_uuid == x["id"],
            PhantomBusterConfig.pb_type == PhantomBusterType.OUTBOUND_ENGINE,
        ).first()
        phantom_map.append(
            {
                "config_id": config and config.id,
                "phantom_name": x["name"],
                "client_id": config and config.client_id,
                "client_sdr_id": config and config.client_sdr_id,
                "google_sheets_uuid": config and config.google_sheets_uuid,
                "phantom_uuid": config and config.phantom_uuid,
                "phantom_id": x["id"],
            }
        )

    return phantom_map
