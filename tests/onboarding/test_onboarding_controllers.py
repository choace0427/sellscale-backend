from app import db, app
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
)
from src.onboarding.services import (
    get_sight_onboarding,
    create_sight_onboarding,
    update_sight_onboarding,
    check_completed_first_persona,
    check_completed_ai_behavior,
    check_completed_first_campaign,
    is_onboarding_complete,
)
from model_import import (SightOnboarding, ResponseConfiguration, GeneratedMessageCTA)
from tests.test_utils.decorators import use_app_context
import json

@use_app_context
def test_check_onboarding():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_archetype = basic_archetype(client=client)
    client_archetype.client_sdr_id=client_sdr.id
    client_prospect = basic_prospect(client=client, archetype=client_archetype)
    onboarding = SightOnboarding(client_sdr_id=client_sdr.id)
    db.session.add(client_archetype)
    db.session.add(onboarding)
    db.session.commit()

    response = app.test_client().post(
        "onboarding/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr.id,
            }
        ),
    )
    assert response.status_code == 200
    response = response.json
    assert response["is_onboarding_complete"] == False
    assert response["completed_first_persona"] == False
    assert response["completed_ai_behavior"] == False
    assert response["completed_first_campaign"] == False
    assert response["completed_go_live"] == False

    onboarding.is_onboarding_complete = True
    db.session.add(onboarding)
    db.session.commit()
    response = app.test_client().post(
        "onboarding/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr.id,
            }
        ),
    )
    assert response.status_code == 200
    response = response.json
    assert response["is_onboarding_complete"] == True


@use_app_context
def test_manual_update_onboarding():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_archetype = basic_archetype(client=client)
    client_archetype.client_sdr_id=client_sdr.id
    client_prospect = basic_prospect(client=client, archetype=client_archetype)
    onboarding = SightOnboarding(client_sdr_id=client_sdr.id)
    db.session.add(client_archetype)
    db.session.add(onboarding)
    db.session.commit()

    response = app.test_client().post(
        "onboarding/update",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr.id,
                "manual_update_key": "completed_first_persona",
            }
        ),
    )
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"
    assert onboarding.is_onboarding_complete == False
    assert onboarding.completed_first_persona == True
