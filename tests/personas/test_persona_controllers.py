from app import app, db

from model_import import (
    Client,
)
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    get_login_token,
)

import json


@use_app_context
def test_split_prospects():
    client: Client = basic_client()
    client_sdr = basic_client_sdr(client)

    source_persona = basic_archetype(client, client_sdr)
    target_persona = basic_archetype(client, client_sdr)

    response = app.test_client().post(
        "personas/split_prospects",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "source_archetype_id": source_persona.id,
                "target_archetype_ids": [target_persona.id],
            }
        ),
    )
    assert response.status_code == 200
