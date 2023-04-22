from app import db, app
import pytest
import json
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_bump_framework,
    get_login_token
)
from decorators import use_app_context
import mock

from model_import import BumpFramework

LOGIN_TOKEN = get_login_token()

# @use_app_context
# def test_create_bump_framework():
#     client = basic_client()
#     client_sdr = basic_client_sdr(client)
#     client_sdr_id = client_sdr.id

#     bump_frameworks: list[BumpFramework] = BumpFramework.query.all()
#     assert len(bump_frameworks) == 0

#     response = app.test_client().post(
#         "/bump_framework/create",
#         headers={"Content-Type": "application/json"},
#         data=json.dumps(
#             {
#                 "description": "Test Bump Framework Description",
#                 "overall_status": "ACCEPTED",
#                 "client_sdr_id": client_sdr_id,
#             }
#         ),
#     )
#     assert response.status_code == 200

#     bump_frameworks: list[BumpFramework] = BumpFramework.query.all()
#     assert len(bump_frameworks) == 1
#     assert bump_frameworks[0].description == "Test Bump Framework Description"
#     assert bump_frameworks[0].overall_status.value == "ACCEPTED"
#     assert bump_frameworks[0].client_sdr_id == client_sdr_id


# @use_app_context
# def test_post_activate_bump_framework():
#     bump_framework = BumpFramework(
#         description="Test Bump Framework Description",
#         overall_status="ACCEPTED",
#     )
#     db.session.add(bump_framework)
#     db.session.commit()

#     assert bump_framework.active == True

#     response = app.test_client().post(
#         "/bump_framework/bump/activate",
#         headers={"Content-Type": "application/json"},
#         data=json.dumps({"bump_framework_id": bump_framework.id}),
#     )
#     assert response.status_code == 200

#     bump_framework = BumpFramework.query.get(bump_framework.id)
#     assert bump_framework.active == False


@use_app_context
def test_get_bump_frameworks():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    bump_framework = basic_bump_framework(client_sdr)

    response = app.test_client().get(
        "/bump_framework/bump?overall_status=ACCEPTED".format(
            client_sdr_id
        ),
        headers={
            "Authorization": "Bearer {token}".format(token=LOGIN_TOKEN)
        },
    )
    assert response.status_code == 200
    response_json = json.loads(response.data)
    assert len(response_json.get('bump_frameworks')) == 0

    response = app.test_client().get(
        "/bump_framework/bump?overall_status=BUMPED".format(
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
