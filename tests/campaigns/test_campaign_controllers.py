from app import db, app
from test_utils import test_app
import pytest
from decorators import use_app_context
import json

from test_utils import basic_client, basic_archetype, basic_client_sdr
from model_import import OutboundCampaign


@use_app_context
def test_create_campaign():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    response = app.test_client().post(
        "campaigns/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
                "campaign_type": "LINKEDIN",
                "ctas": [5, 6],
                "client_archetype_id": archetype.id,
                "client_sdr_id": client_sdr.id,
                "campaign_start_date": "2021-01-01",
                "campaign_end_date": "2021-01-01",
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = json.loads(response.data.decode("utf-8"))["campaign_id"]
    assert campaign_id > 0

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.id == campaign_id
    assert campaign.client_archetype_id == archetype.id
    assert campaign.client_sdr_id == client_sdr.id
    assert campaign.campaign_type.value == "LINKEDIN"
    assert campaign.prospect_ids == [1, 2, 3, 4]
    assert campaign.ctas == [5, 6]
    assert campaign.status.value == "PENDING"
