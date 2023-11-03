from app import db, app
from tests.test_utils.test_utils import test_app
from tests.test_utils.decorators import use_app_context
import json

from src.response_ai.models import ResponseConfiguration
from tests.test_utils.test_utils import basic_client, basic_archetype


@use_app_context
def test_create_response_ai_configuration():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    response = app.test_client().post(
        "/response_ai/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "archetype_id": archetype_id,
                "li_first_follow_up": "li_first_follow_up",
                "li_second_follow_up": "li_second_follow_up",
                "li_third_follow_up": "li_third_follow_up",
            }
        ),
    )
    assert response.status_code == 200
    assert json.loads(response.data.decode("utf-8")) == {
        "response_configuration_id": archetype_id
    }

    response_configuration = ResponseConfiguration.query.filter_by(
        archetype_id=archetype_id
    ).first()
    assert response_configuration is not None
    assert response_configuration.li_first_follow_up == "li_first_follow_up"
    assert response_configuration.li_second_follow_up == "li_second_follow_up"
    assert response_configuration.li_third_follow_up == "li_third_follow_up"


@use_app_context
def test_get_response_ai_configuration():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id

    response_configuration = ResponseConfiguration(
        archetype_id=archetype_id,
        li_first_follow_up="li_first_follow_up",
        li_second_follow_up="li_second_follow_up",
        li_third_follow_up="li_third_follow_up",
    )
    db.session.add(response_configuration)
    db.session.commit()

    rc_list = ResponseConfiguration.query.all()
    assert len(rc_list) == 1

    response = app.test_client().get(
        "/response_ai/?archetype_id={}".format(archetype_id),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert json.loads(response.data.decode("utf-8")) == {
        "archetype_id": archetype_id,
        "li_first_follow_up": "li_first_follow_up",
        "li_second_follow_up": "li_second_follow_up",
        "li_third_follow_up": "li_third_follow_up",
    }


@use_app_context
def test_update_response_configuration():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id

    response_configuration = ResponseConfiguration(
        archetype_id=archetype_id,
        li_first_follow_up="li_first_follow_up",
        li_second_follow_up="li_second_follow_up",
        li_third_follow_up="li_third_follow_up",
    )
    db.session.add(response_configuration)
    db.session.commit()

    rc_list = ResponseConfiguration.query.all()
    assert len(rc_list) == 1

    response = app.test_client().post(
        "/response_ai/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "archetype_id": archetype_id,
                "li_first_follow_up": "li_first_follow_up_updated",
                "li_second_follow_up": "li_second_follow_up_updated",
                "li_third_follow_up": "li_third_follow_up_updated",
            }
        ),
    )
    assert response.status_code == 200
    assert json.loads(response.data.decode("utf-8")) == {
        "response_configuration_id": archetype_id
    }
