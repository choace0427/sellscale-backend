from src.client.services import (
    create_client,
    get_client,
    create_client_archetype,
    create_client_sdr,
    reset_client_sdr_sight_auth_token,
)
from model_import import Client, ClientArchetype, ClientSDR
from decorators import use_app_context
from test_utils import test_app


@use_app_context
def test_add_client_and_archetype():
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

    create_client_sdr(client_id=c.id, name="testing", email="testing")
    client_sdrs: list = ClientSDR.query.all()
    assert len(client_sdrs) == 1

    reset_client_sdr_sight_auth_token(client_sdr_id=client_sdrs[0].id)
    client_sdrs: ClientSDR = ClientSDR.query.get(client_sdrs[0].id)
    assert client_sdrs.auth_token is not None
