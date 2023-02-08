from app import db, app
from test_utils import test_app
from model_import import Echo, Prospect, ProspectStatus
from datetime import datetime, timedelta
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
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client=client)
    client_sdr_id = client_sdr.id

    statuses = [
        ProspectStatus.ACCEPTED,
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
    ]

    # creates 3 standard prospects (all counted)
    for status in statuses:
        prospect = basic_prospect(client=client, archetype=archetype)
        prospect.status = status
        prospect.client_sdr_id = client_sdr_id
        db.session.add(prospect)
        db.session.commit()

    for status in statuses:
        # creates 1 prospect who we reviewed < 24 hours ago. not counted
        prospect = basic_prospect(client=client, archetype=archetype)
        prospect.status = status
        prospect.client_sdr_id = client_sdr_id
        prospect.last_reviewed = datetime.now()
        db.session.add(prospect)
        db.session.commit()

        # creates 1 prospect who we reviewed > 24 hours ago. counted!
        prospect = basic_prospect(client=client, archetype=archetype)
        prospect.status = status
        prospect.client_sdr_id = client_sdr_id
        prospect.last_reviewed = datetime.now() - timedelta(days=4)
        db.session.add(prospect)
        db.session.commit()

    prospects: list = Prospect.query.all()
    assert len(prospects) == 12

    response = app.test_client().get("/sight_inbox/{}".format(client_sdr_id))
    assert response.status_code == 200
    inbox = json.loads(response.data.decode("utf-8"))
    assert len([x for x in inbox if x["prospect_status"] == "ACCEPTED"]) == 3
    assert len([x for x in inbox if x["prospect_status"] == "RESPONDED"]) == 2
    assert len([x for x in inbox if x["prospect_status"] == "ACTIVE_CONVO"]) == 2
    assert len([x for x in inbox if x["prospect_status"] == "SCHEDULING"]) == 2
    assert len(inbox) == 9

    prospect0 = inbox[0]
    assert prospect0["prospect_id"] > 1
    assert prospect0["prospect_full_name"] == "Testing Testasara"
    assert prospect0["prospect_title"] == "Testing Director"
    assert prospect0["prospect_linkedin"] == None
    assert prospect0["prospect_linkedin_conversation_thread"] == ""
    assert prospect0["prospect_sdr_name"] == "Test SDR"
    assert prospect0["prospect_client_name"] == "Testing Company"
    assert prospect0["prospect_status"] == "ACCEPTED"
    assert prospect0["actions"] == ["RECORD_BUMP"]
    assert not prospect0["prospect_deactivate_ai_engagement"]
    assert prospect0["prospect_archetype_id"] == archetype_id
