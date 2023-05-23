from app import app
import json
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_bump_framework,
    get_login_token
)
from decorators import use_app_context

LOGIN_TOKEN = get_login_token()


@use_app_context
def test_get_bump_frameworks():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    bump_framework = basic_bump_framework(client_sdr)

    response = app.test_client().get(
        "/bump_framework/bump?overall_statuses=ACCEPTED,ACTIVE_CONVO&archetype_ids=",
        headers={
            "Authorization": "Bearer {token}".format(token=LOGIN_TOKEN)
        },
    )
    assert response.status_code == 200
    response_json = json.loads(response.data)
    assert len(response_json.get('bump_frameworks')) == 0

    response = app.test_client().get(
        "/bump_framework/bump?overall_statuses=BUMPED&archetype_ids=".format(
            client_sdr_id
        ),
        headers={
            "Authorization": "Bearer {token}".format(token=LOGIN_TOKEN)
        },
    )
    assert response.status_code == 200
    response_json = json.loads(response.data)
    assert len(response_json.get('bump_frameworks')) == 1
    assert response_json.get('bump_frameworks')[0].get('id') == bump_framework.id
