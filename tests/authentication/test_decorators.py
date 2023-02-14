from app import app, db
from test_utils import (
    basic_client,
    basic_client_sdr,
    test_app,
    get_login_token)
from decorators import use_app_context

import json


@use_app_context
def test_get_client_sdr_id():
    client = basic_client()
    client_sdr = basic_client_sdr(client)

    no_header_response = app.test_client().get(
        "auth/get_client_sdr_name",
        headers={
            "Content-Type": "application/json"
        },
    )
    assert no_header_response.status_code == 401
    assert no_header_response.json.get("message") == "Authorization header is missing."

    bad_header_response = app.test_client().get(
        "auth/get_client_sdr_name",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer",
        },
    )
    assert bad_header_response.status_code == 401
    assert bad_header_response.json.get("message") == "Bearer token is missing."

    bad_token_response = app.test_client().get(
        "auth/get_client_sdr_name",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format("bad_token"),
        },
    )
    assert bad_token_response.status_code == 401
    assert bad_token_response.json.get("message") == "Authentication token is invalid."

    response = app.test_client().get(
        "auth/get_client_sdr_name",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert response.status_code == 200
    assert response.json == client_sdr.name


