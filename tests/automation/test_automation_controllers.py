from app import db, app
import pytest
from decorators import use_app_context
import json
from test_utils import test_app, basic_client, basic_client_sdr


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
