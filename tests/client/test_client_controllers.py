from src.client.services import (
    create_client,
    get_client,
    create_client_archetype,
    create_client_sdr,
    reset_client_sdr_sight_auth_token,
)
from model_import import Client, ClientArchetype, ClientSDR, GNLPModel
from decorators import use_app_context
from test_utils import test_app, basic_client, basic_client_sdr
from app import app, db
import json
import mock


@use_app_context
@mock.patch("src.client.services.make_stytch_call")
def test_send_magic_link(make_stytch_call_mock):
    """Test that we can send a magic link to a client SDR."""
    client: Client = basic_client()
    client_sdr: ClientSDR = basic_client_sdr(client=client)

    response = app.test_client().post(
        "client/send_magic_link_login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_email": client_sdr.email,
            }
        ),
    )
    assert response.status_code == 200
    assert make_stytch_call_mock.called


@use_app_context
def approve_auth_token():
    """Test that we can approve an auth token after getting from Stytch provider"""
    client: Client = basic_client()
    client_sdr: ClientSDR = basic_client_sdr(client=client)
    client_sdr_email: str = client_sdr.email

    response = app.test_client().post(
        "client/approve_auth_token",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_email": client_sdr_email,
                "token": "1234",
            }
        ),
    )
    assert response.status_code == 200
    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    assert client_sdr.auth_token == "1234"
