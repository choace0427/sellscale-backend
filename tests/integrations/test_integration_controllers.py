from app import app, db
from model_import import Client, ClientArchetype, ClientSDR, ResearchPointType
from decorators import use_app_context
from test_utils import (
    test_app,
    get_login_token,
    basic_client,
    basic_archetype,
    basic_client_sdr,
)

import json
import mock

@use_app_context
#@mock.patch("src.utils.slack.send_slack_message")
def test_post_linkedin_credentials():
    """Tests the sending LinkedIn credentials endpoint.

    Args:
        UNUSED - mock_send_slack_message (Mock): Mocks the send_slack_message function.
    """

    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    response = app.test_client().post(
        "integration/linkedin/send-credentials",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "username": "Test Name",
                "password": "Test Password"
            }
        ),
    )
    assert response.status_code == 200
    #assert mock_send_slack_message.call_count == 1
