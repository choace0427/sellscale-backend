import mock
from app import app, db

from model_import import Client, PersonaSplitRequestTask, PersonaSplitRequest
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    get_login_token,
    basic_prospect,
)

import json


@use_app_context
@mock.patch("src.personas.services.process_persona_split_request_task.apply_async")
def test_split_prospects(process_persona_split_request_task_split):
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

    persona_split_requests = PersonaSplitRequest.query.all()
    assert len(persona_split_requests) == 1
    persona_split_request_tasks = PersonaSplitRequestTask.query.all()
    assert len(persona_split_request_tasks) == 0

    prospect = basic_prospect(
        client=client,
        archetype=source_persona,
        client_sdr=client_sdr,
    )

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

    persona_split_requests = PersonaSplitRequest.query.all()
    assert len(persona_split_requests) == 2
    persona_split_request_tasks = PersonaSplitRequestTask.query.all()
    assert len(persona_split_request_tasks) == 1

    response = app.test_client().get(
        "personas/recent_split_requests?source_archetype_id=" + str(source_persona.id),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    assert len(response.json["recent_requests"]) == 1
    split_request_id = response.json["recent_requests"][0]["id"]

    response = app.test_client().get(
        "personas/split_request?split_request_id=" + str(split_request_id),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    assert response.json["details"] is not None
