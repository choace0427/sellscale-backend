from app import app
import pytest
from decorators import use_app_context
from test_utils import test_app
from test_utils import basic_client


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
