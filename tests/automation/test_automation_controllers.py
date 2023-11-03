from app import db, app
import pytest
from tests.test_utils.decorators import use_app_context
import json
from tests.test_utils.test_utils import test_app, basic_client, basic_client_sdr
import mock


class FakePostResponse:
    def __init__(self, return_payload={"id": "TEST_ID"}):
        self.payload = return_payload

    def json(self):
        return self.payload


@use_app_context
@mock.patch(
    "src.automation.services.requests.request",
    return_value=FakePostResponse(),
)
@mock.patch(
    "src.automation.services.requests.get",
    return_value=FakePostResponse(return_payload=[]),
)
@mock.patch(
    "src.automation.services.requests.post",
    return_value=FakePostResponse(return_payload=[]),
)
def test_configure_phantom_agents(request_post_patch, request_get_patch, request_patch):
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
@mock.patch(
    "src.automation.controllers.update_phantom_buster_li_at",
    return_value=(200, "Success"),
)
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
