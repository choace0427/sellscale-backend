from app import db, app
from test_utils import (
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
from decorators import use_app_context

@use_app_context
def test_get_sight_onboarding():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    
    sight_onboarding : SightOnboarding = SightOnboarding(client_sdr_id=client_sdr.id)
    db.session.add(sight_onboarding)
    db.session.commit()

    sight_onboarding = get_sight_onboarding(client_sdr_id=client_sdr.id)
    assert sight_onboarding.client_sdr_id == client_sdr.id
    assert sight_onboarding.is_onboarding_complete == False
    assert sight_onboarding.completed_credentials == False
    assert sight_onboarding.completed_first_persona == False
    assert sight_onboarding.completed_ai_behavior == False
    assert sight_onboarding.completed_first_campaign == False
    assert sight_onboarding.completed_go_live == False


@use_app_context
def test_create_sight_onboarding():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_sdr2 = basic_client_sdr(client=client)

    # Test that we can create a new sight onboarding, defaults to False
    create_sight_onboarding(client_sdr_id=client_sdr.id)
    sight_onboarding = SightOnboarding.query.filter_by(client_sdr_id=client_sdr.id).first()
    assert sight_onboarding.client_sdr_id == client_sdr.id
    assert sight_onboarding.is_onboarding_complete == False
    assert sight_onboarding.completed_credentials == False
    assert sight_onboarding.completed_first_persona == False
    assert sight_onboarding.completed_ai_behavior == False
    assert sight_onboarding.completed_first_campaign == False
    assert sight_onboarding.completed_go_live == False

    # Test that we can create a new sight onboarding, but set to True for `is_onboarding_complete = True`
    create_sight_onboarding(client_sdr_id=client_sdr2.id, is_onboarding_complete=True)
    sight_onboarding = SightOnboarding.query.filter_by(client_sdr_id=client_sdr2.id).first()
    assert sight_onboarding.client_sdr_id == client_sdr2.id
    assert sight_onboarding.is_onboarding_complete == True
    assert sight_onboarding.completed_credentials == True
    assert sight_onboarding.completed_first_persona == True
    assert sight_onboarding.completed_ai_behavior == True
    assert sight_onboarding.completed_first_campaign == True
    assert sight_onboarding.completed_go_live == True


@use_app_context
def test_update_sight_onboarding():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)

    sight_onboarding: SightOnboarding = SightOnboarding(client_sdr_id=client_sdr.id)
    db.session.add(sight_onboarding)
    db.session.commit()

    assert sight_onboarding.is_onboarding_complete == False
    assert sight_onboarding.completed_credentials == False
    update_sight_onboarding(client_sdr_id=client_sdr.id, manual_update_key="completed_credentials")
    assert sight_onboarding.is_onboarding_complete == False
    assert sight_onboarding.completed_credentials == True

    update_sight_onboarding(client_sdr_id=client_sdr.id, manual_update_key="completed_first_persona")
    assert sight_onboarding.is_onboarding_complete == False
    update_sight_onboarding(client_sdr_id=client_sdr.id, manual_update_key="completed_ai_behavior")
    assert sight_onboarding.is_onboarding_complete == False
    update_sight_onboarding(client_sdr_id=client_sdr.id, manual_update_key="completed_first_campaign")
    assert sight_onboarding.is_onboarding_complete == False
    update_sight_onboarding(client_sdr_id=client_sdr.id, manual_update_key="completed_go_live")
    assert sight_onboarding.is_onboarding_complete == True


@use_app_context
def test_check_completed_credentials():
    # TODO: NEEDS WORK
    pass


@use_app_context
def test_check_completed_first_persona():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    assert check_completed_first_persona(client_sdr_id=client_sdr.id) == False

    client_archetype = basic_archetype(client=client)
    client_archetype.client_sdr_id = client_sdr.id
    db.session.add(client_archetype)
    db.session.commit()
    assert check_completed_first_persona(client_sdr_id=client_sdr.id) == False
    for i in range(10):
        prospect = basic_prospect(client=client, archetype=client_archetype)
        db.session.add(prospect)
        db.session.commit()
    assert check_completed_first_persona(client_sdr_id=client_sdr.id) == True


@use_app_context
def test_check_completed_ai_behavior():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    assert check_completed_ai_behavior(client=client, client_sdr_id=client_sdr.id) == False

    client2 = basic_client()
    client2.linkedin_outbound_enabled = True
    client_sdr2 = basic_client_sdr(client=client2)
    client_sdr2.scheduling_link = "test-link"
    assert check_completed_ai_behavior(client=client2, client_sdr_id=client_sdr2.id) == False

    client_archetype = basic_archetype(client=client)
    client_archetype.client_sdr_id = client_sdr2.id
    ai_config = ResponseConfiguration(archetype_id = client_archetype.id)
    db.session.add(client_archetype)
    db.session.add(ai_config)
    db.session.commit()
    assert check_completed_ai_behavior(client=client2, client_sdr_id=client_sdr2.id) == True


@use_app_context
def test_check_completed_first_campaign():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    assert check_completed_first_campaign(client_sdr_id=client_sdr.id) == False

    client_archetype = basic_archetype(client=client)
    client_archetype.client_sdr_id = client_sdr.id
    db.session.add(client_archetype)
    db.session.commit()
    for i in range(3):
        cta = GeneratedMessageCTA(archetype_id=client_archetype.id, text_value="test {}".format(i+1))
        db.session.add(cta)
        db.session.commit()
    assert check_completed_first_campaign(client_sdr_id=client_sdr.id) == False
    fourth_cta = GeneratedMessageCTA(archetype_id=client_archetype.id,  text_value="test 4")
    db.session.add(fourth_cta)
    db.session.commit()
    assert check_completed_first_campaign(client_sdr_id=client_sdr.id) == True


@use_app_context
def test_is_onboarding_complete():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_sdr2 = basic_client_sdr(client=client)

    sight_onboarding: SightOnboarding = SightOnboarding(client_sdr_id=client_sdr.id)
    sight_onboarding2: SightOnboarding = SightOnboarding(client_sdr_id=client_sdr2.id, is_onboarding_complete=True)
    db.session.add(sight_onboarding)
    db.session.add(sight_onboarding2)
    db.session.commit()

    assert is_onboarding_complete(client_sdr_id=client_sdr.id) == {
        "is_onboarding_complete": False,
        "completed_credentials": False,
        "completed_first_persona": False,
        "completed_ai_behavior": False,
        "completed_first_campaign": False,
        "completed_go_live": False
    }
    assert is_onboarding_complete(client_sdr_id=client_sdr2.id) == {
        "is_onboarding_complete": True,
        "completed_credentials": False,
        "completed_first_persona": False,
        "completed_ai_behavior": False,
        "completed_first_campaign": False,
        "completed_go_live": False
    }
    