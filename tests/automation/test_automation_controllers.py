from app import db, app
import pytest
from decorators import use_app_context
import json
from test_utils import test_app, basic_client, basic_client_sdr
import mock


@use_app_context
def test_post_phantom_buster_config():
    client = basic_client()
    client_id = client.id
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id

    response = app.test_client().post(
        "/automation/create/phantom_buster_config",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client_id,
                "client_sdr_id": sdr_id,
                "google_sheets_uuid": "test_google_sheets_uuid",
                "phantom_name": "test_phantom_name",
                "phantom_uuid": "test_phantom_uuid",
            }
        ),
    )
    assert response.status_code == 200


class FakePostResponse:
    def json(self):
        return {"id": "TEST_ID"}


@use_app_context
@mock.patch(
    "src.automation.services.requests.request",
    return_value=FakePostResponse(),
)
def test_configure_phantom_agents(request_patch):
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id

    response = app.test_client().post(
        "/automation/configure_phantom_agents",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": sdr_id,
                "linkedin_session_cookie": "TEST_LINKEDIN_COOKIE",
                "google_sheet_uuid": "GOOGLE_SHEET_UUID",
            }
        ),
    )
    assert response.status_code == 200
    assert request_patch.call_count == 2


@use_app_context
@mock.patch("src.automation.controllers.update_phantom_buster_li_at", return_value=(200, "Success"))
def test_update_phantom_li_at(update_phantom_buster_li_at_mock):
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id

    response = app.test_client().post(
        "/automation/update_phantom_li_at",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": sdr_id,
                "linkedin_authentication_token": "TEST_LINKEDIN_AT_TOKEN",
            }
        ),
    )
    assert response.status_code == 200
    assert update_phantom_buster_li_at_mock.call_count == 1
