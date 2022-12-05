from app import db, app
from test_utils import test_app
from decorators import use_app_context
import json

from src.response_ai.models import ResponseConfiguration
from test_utils import basic_client, basic_archetype


@use_app_context
def test_response_ai_route():
    response = app.test_client().get("/response_ai/")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"


@use_app_context
def test_create_response_ai_configuration():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    response = app.test_client().post(
        "/response_ai/create",
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
