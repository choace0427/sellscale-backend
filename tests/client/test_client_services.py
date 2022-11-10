from src.client.services import (
    create_client,
    get_client,
    create_client_archetype,
    create_client_sdr,
    reset_client_sdr_sight_auth_token,
)
from model_import import Client, ClientArchetype, ClientSDR, GNLPModel
from decorators import use_app_context
from test_utils import test_app
from app import app
import json


@use_app_context
def test_add_client_and_archetype():
    response = app.test_client().get("client/")
    assert response.status_code == 200

    create_client(
        company="testing",
        contact_name="testing",
        contact_email="testing",
    )
    clients: list = Client.query.all()
    assert len(clients) == 1

    response = app.test_client().post(
        "client/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "company": "testing",
                "contact_name": "testing",
                "contact_email": "testing",
            }
        ),
    )
    assert response.status_code == 200

    clients: list = Client.query.all()
    assert len(clients) == 1

    c: Client = get_client(clients[0].id)
    assert c.id == clients[0].id
    assert len(c.notification_allowlist) == 3

    response = app.test_client().post(
        "client/archetype",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": c.id,
                "archetype": "testing",
                "filters": {},
            }
        ),
    )
    assert response.status_code == 200

    client_archetypes: list = ClientArchetype.query.all()
    assert len(client_archetypes) == 1

    gnlp_models: list = GNLPModel.query.all()
    assert len(gnlp_models) == 1


@use_app_context
def test_add_client_and_archetype_and_sdr():

    create_client(
        company="testing",
        contact_name="testing",
        contact_email="testing",
    )
    clients: list = Client.query.all()
    assert len(clients) == 1

    create_client(
        company="testing",
        contact_name="testing",
        contact_email="testing",
    )
    clients: list = Client.query.all()
    assert len(clients) == 1

    c: Client = get_client(clients[0].id)
    assert c.id == clients[0].id

    create_client_archetype(client_id=c.id, archetype="testing", filters={})

    client_archetypes: list = ClientArchetype.query.all()
    assert len(client_archetypes) == 1

    response = app.test_client().post(
        "client/sdr",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": c.id,
                "name": "testing",
                "email": "testing",
            }
        ),
    )
    assert response.status_code == 200

    client_sdrs: list = ClientSDR.query.all()
    assert len(client_sdrs) == 1

    response = app.test_client().post(
        "client/reset_client_sdr_auth_token",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdrs[0].id,
            }
        ),
    )
    assert response.status_code == 200
    client_sdrs: ClientSDR = ClientSDR.query.get(client_sdrs[0].id)
    assert client_sdrs.auth_token is not None
