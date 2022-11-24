from app import db, app
from test_utils import test_app
from model_import import Echo, Prospect, ProspectStatus
import pytest
from config import TestingConfig
from decorators import use_app_context
from test_utils import basic_client, basic_client_sdr, basic_prospect, basic_archetype
import json


@use_app_context
def test_get_empty_client_sdr_inbox():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_sdr_id = client_sdr.id

    response = app.test_client().get("/sight_inbox/{}".format(client_sdr_id))
    assert response.status_code == 200
    assert json.loads(response.data.decode("utf-8")) == []


@use_app_context
def test_get_one_accepted_prospect():
    client = basic_client()
    archetype = basic_archetype(client=client)
    client_sdr = basic_client_sdr(client=client)
    client_sdr_id = client_sdr.id
    prospect = basic_prospect(client=client, archetype=archetype)
    prospect.status = ProspectStatus.ACCEPTED
    prospect.client_sdr_id = client_sdr_id
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().get("/sight_inbox/{}".format(client_sdr_id))
    assert response.status_code == 200
    inbox = json.loads(response.data.decode("utf-8"))
    assert len(inbox) == 1
    assert inbox[0]["prospect_id"] == prospect.id
    assert inbox[0]["prospect_full_name"] == prospect.full_name
    assert inbox[0]["prospect_title"] == prospect.title
    assert inbox[0]["prospect_linkedin"] == prospect.linkedin_url
    assert (
        inbox[0]["prospect_linkedin_conversation_thread"]
        == prospect.li_conversation_thread_id
    )
    assert inbox[0]["prospect_sdr_name"] == client_sdr.name
    assert inbox[0]["prospect_client_name"] == client.company
    assert inbox[0]["prospect_last_reviwed_date"] == prospect.last_reviewed
    assert inbox[0]["actions"] == ["RECORD_BUMP"]
