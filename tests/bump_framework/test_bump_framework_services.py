from app import db, app
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_bump_framework,
    )
from decorators import use_app_context
from src.bump_framework.services import (
    get_bump_frameworks_for_sdr,
    create_bump_framework,
    modify_bump_framework,
    deactivate_bump_framework,
    activate_bump_framework,
)

from model_import import ProspectOverallStatus, BumpFramework


@use_app_context
def test_get_bump_frameworks_for_sdr():
    client = basic_client()
    sdr = basic_client_sdr(client)
    bump_framework = basic_bump_framework(sdr, active=True)
    bump_framework2 = basic_bump_framework(sdr, active=False)

    bumps = get_bump_frameworks_for_sdr(sdr.id, bump_framework.overall_status)
    assert len(bumps) == 1
    assert bumps[0]["id"] == bump_framework.id

    bumps = get_bump_frameworks_for_sdr(sdr.id, bump_framework.overall_status, activeOnly=False)
    assert len(bumps) == 2
    assert bumps[0]["id"] == bump_framework.id
    assert bumps[1]["id"] == bump_framework2.id


@use_app_context
def test_create_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)

    create_bump_framework(sdr.id, "title", "description", ProspectOverallStatus.ACTIVE_CONVO, True, True)
    assert BumpFramework.query.count() == 1
    bump_framework: BumpFramework = BumpFramework.query.filter_by(client_sdr_id=sdr.id).first()
    assert bump_framework.title == "title"
    assert bump_framework.description == "description"
    assert bump_framework.overall_status == ProspectOverallStatus.ACTIVE_CONVO
    assert bump_framework.active == True
    assert bump_framework.default == True


@use_app_context
def test_modify_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    bump_framework = basic_bump_framework(sdr, active=True)

    modify_bump_framework(sdr.id, bump_framework.id, "new title", "new description", True)
    bump_framework: BumpFramework = BumpFramework.query.filter_by(client_sdr_id=sdr.id).first()
    assert bump_framework.title == "new title"
    assert bump_framework.description == "new description"
    assert bump_framework.default == True


@use_app_context
def test_deactivate_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    bump_framework = basic_bump_framework(sdr, active=True)

    deactivate_bump_framework(sdr.id, bump_framework.id)
    bump_framework: BumpFramework = BumpFramework.query.filter_by(client_sdr_id=sdr.id).first()
    assert bump_framework.active == False


@use_app_context
def test_activate_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    bump_framework = basic_bump_framework(sdr, active=False)

    activate_bump_framework(sdr.id, bump_framework.id)
    bump_framework: BumpFramework = BumpFramework.query.filter_by(client_sdr_id=sdr.id).first()
    assert bump_framework.active == True
