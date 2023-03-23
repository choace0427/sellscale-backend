from test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_client_sdr,
    basic_prospect,
    basic_prospect_email,
    basic_outbound_campaign,
)
from decorators import use_app_context
from freezegun import freeze_time
from datetime import datetime, timedelta
from model_import import (
    GeneratedMessageType
)
from src.campaigns.autopilot.services import (
    get_sla_count
)


@use_app_context
def test_get_sla_count():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    oc = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr
    )

    # Last monday is 2 weeks before the campaign start date, which is set to next monday.
    last_monday = oc.campaign_start_date - timedelta(days=14)
    sla_count = get_sla_count(client_sdr.id, archetype.id, GeneratedMessageType.EMAIL, last_monday)
    assert sla_count == 1

    # Next monday is 1 week before the campaign start date, which is set to next monday.
    this_monday = oc.campaign_start_date - timedelta(days=7)
    sla_count = get_sla_count(client_sdr.id, archetype.id, GeneratedMessageType.EMAIL, this_monday)
    assert sla_count == 0
