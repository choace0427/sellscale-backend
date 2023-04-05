from app import db, app
import pytest
import json
from test_utils import test_app, basic_client, basic_client_sdr
from decorators import use_app_context
import mock

from model_import import BumpFramework


@use_app_context
def test_create_bump_framework():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    bump_frameworks: list[BumpFramework] = BumpFramework.query.all()
    assert len(bump_frameworks) == 0

    response = app.test_client().post(
        "/bump_framework/create",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "description": "Test Bump Framework Description",
                "overall_status": "ACCEPTED",
                "client_sdr_id": client_sdr_id,
            }
        ),
    )
    assert response.status_code == 200

    bump_frameworks: list[BumpFramework] = BumpFramework.query.all()
    assert len(bump_frameworks) == 1
    assert bump_frameworks[0].description == "Test Bump Framework Description"
    assert bump_frameworks[0].overall_status.value == "ACCEPTED"
    assert bump_frameworks[0].client_sdr_id == client_sdr_id


@use_app_context
def test_delete_bump_framework():
    bump_framework = BumpFramework(
        description="Test Bump Framework Description",
        overall_status="ACCEPTED",
    )
    db.session.add(bump_framework)
    db.session.commit()

    bump_frameworks: list[BumpFramework] = BumpFramework.query.all()
    assert len(bump_frameworks) == 1

    response = app.test_client().delete(
        "/bump_framework/",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"bump_framework_id": bump_framework.id}),
    )
    assert response.status_code == 200

    bump_frameworks: list[BumpFramework] = BumpFramework.query.all()
    assert len(bump_frameworks) == 0


@use_app_context
def test_toggle_bump_framework_active():
    bump_framework = BumpFramework(
        description="Test Bump Framework Description",
        overall_status="ACCEPTED",
    )
    db.session.add(bump_framework)
    db.session.commit()

    assert bump_framework.active == True

    response = app.test_client().post(
        "/bump_framework/toggle_active",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"bump_framework_id": bump_framework.id}),
    )
    assert response.status_code == 200

    bump_framework = BumpFramework.query.get(bump_framework.id)
    assert bump_framework.active == False


@use_app_context
def test_get_bump_frameworks():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    bump_framework = BumpFramework(
        description="Test Bump Framework Description",
        overall_status="ACCEPTED",
        client_sdr_id=client_sdr_id,
    )
    db.session.add(bump_framework)
    db.session.commit()

    response = app.test_client().get(
        "/bump_framework/?overall_status=ACCEPTED&client_sdr_id={}".format(
            client_sdr_id
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    response_json = json.loads(response.data)
    assert len(response_json) == 1
