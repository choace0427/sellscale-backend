from app import app
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_prospect,
    basic_archetype,
)
from model_import import ProspectStatus, ProspectOverallStatus
from src.analytics.services import get_sdr_pipeline_all_details

import json


@use_app_context
def test_get_sdr_pipeline_all_details():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(
        client,
        archetype,
        client_sdr,
        overall_status=ProspectOverallStatus.SENT_OUTREACH,
    )
    prospect_2 = basic_prospect(
        client,
        archetype,
        client_sdr,
        overall_status=ProspectOverallStatus.SENT_OUTREACH,
    )
    prospect_3 = basic_prospect(
        client, archetype, client_sdr, overall_status=ProspectOverallStatus.ACCEPTED
    )
    prospect_4 = basic_prospect(
        client, archetype, client_sdr, overall_status=ProspectOverallStatus.ACTIVE_CONVO
    )
    prospect_5 = basic_prospect(
        client, archetype, client_sdr, overall_status=ProspectOverallStatus.REMOVED
    )

    details = get_sdr_pipeline_all_details(client_sdr_id=client_sdr.id)
    assert details == {
        "prospected": 5,
        "not_qualified": 0,
        "queued_for_outreach": 0,
        "send_outreach_failed": 0,
        "sent_outreach": 0,
        "accepted": 0,
        "responded": 0,
        "active_convo": 0,
        "scheduling": 0,
        "not_interested": 0,
        "demo_set": 0,
        "demo_won": 0,
        "demo_loss": 0,
        "active_convo_question": 0,
        "active_convo_qual_needed": 0,
        "active_convo_objection": 0,
        "active_convo_next_steps": 0,
        "active_convo_scheduling": 0,
        "active_convo_revival": 0,
        "LINKEDIN": {
            "prospected": 5,
            "not_qualified": 0,
            "queued_for_outreach": 0,
            "send_outreach_failed": 0,
            "sent_outreach": 0,
            "accepted": 0,
            "responded": 0,
            "active_convo": 0,
            "scheduling": 0,
            "not_interested": 0,
            "demo_set": 0,
            "demo_won": 0,
            "demo_loss": 0,
            "active_convo_question": 0,
            "active_convo_qual_needed": 0,
            "active_convo_objection": 0,
            "active_convo_next_steps": 0,
            "active_convo_scheduling": 0,
            "active_convo_revival": 0
        },
        "SELLSCALE": {
            "PROSPECTED": 0,
            "SENT_OUTREACH": 2,
            "ACCEPTED": 1,
            "BUMPED": 0,
            "ACTIVE_CONVO": 1,
            "DEMO": 0,
            "REMOVED": 1
        },
        "EMAIL": {
            "UNKNOWN": 0,
            "NOT_SENT": 0,
            "BOUNCED": 0,
            "SENT_OUTREACH": 0,
            "EMAIL_OPENED": 0,
            "ACCEPTED": 0,
            "ACTIVE_CONVO": 0,
            "SCHEDULING": 0,
            "QUEUED_FOR_OUTREACH": 0,
            "NOT_INTERESTED": 0,
            "UNSUBSCRIBED": 0,
            "DEMO_SET": 0,
            "DEMO_WON": 0,
            "DEMO_LOST": 0
        }
    }
