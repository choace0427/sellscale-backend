from app import app
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_prospect,
    basic_archetype
)
from model_import import ProspectStatus
from src.analytics.services import get_sdr_pipeline_all_details

import json


@use_app_context
def test_get_sdr_pipeline_all_details():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.SENT_OUTREACH)
    prospect_2 = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.SENT_OUTREACH)
    prospect_3 = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.ACCEPTED)
    prospect_4 = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.RESPONDED)
    prospect_5 = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.NOT_INTERESTED)

    details = get_sdr_pipeline_all_details(client_sdr_id=client_sdr.id)
    assert details == {
        "prospected": 0,
        "not_qualified": 0,
        "sent_outreach": 2,
        "accepted": 1,
        "responded": 1,
        "active_convo": 0,
        "scheduling": 0,
        "not_interested": 1,
        "demo_set": 0,
        "demo_won": 0,
        "demo_loss": 0,
    }

