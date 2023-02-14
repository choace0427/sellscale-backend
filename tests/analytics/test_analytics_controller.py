from app import app
import pytest
from decorators import use_app_context
from test_utils import (
    test_app,
    get_login_token,
    basic_client,
    basic_client_sdr,
    basic_prospect,
    basic_archetype,
)
from model_import import ProspectStatus


@use_app_context
def test_get_analytics():
    response = app.test_client().get("/analytics/")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"


@use_app_context
def test_get_latest_weeks_benchmarks():
    response = app.test_client().get("/analytics/latest_weeks_benchmarks")
    assert response.status_code == 200
    assert response.json == []


@use_app_context
def test_get_weekly_li_benchmarks():
    client = basic_client()
    response = app.test_client().get(
        "/analytics/weekly_li_benchmarks?client_id=" + str(client.id)
    )
    assert response.status_code == 200
    assert len(response.json) > 0


@use_app_context
def test_get_all_pipeline_details():
    client = basic_client()
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.SENT_OUTREACH)
    prospect_2 = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.SENT_OUTREACH)
    prospect_3 = basic_prospect(client, archetype, client_sdr, status=ProspectStatus.ACCEPTED)

    response = app.test_client().get(
        "/analytics/pipeline/all_details",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        }
    )
    print(response)
    assert response.status_code == 200
    assert response.json == {
        "message": "Success",
        "pipeline_data": {
            "prospected": 0,
            "not_qualified": 0,
            "sent_outreach": 2,
            "accepted": 1,
            "responded": 0,
            "active_convo": 0,
            "scheduling": 0,
            "not_interested": 0,
            "demo_set": 0,
            "demo_won": 0,
            "demo_loss": 0,
        }
    }
