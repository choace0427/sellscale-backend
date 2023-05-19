from app import db, app
from src.bump_framework.models import BumpLength, JunctionBumpFrameworkClientArchetype
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
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

    bumps = get_bump_frameworks_for_sdr(
        sdr.id, bump_framework.overall_status, activeOnly=False
    )
    assert len(bumps) == 2
    assert bumps[0]["id"] == bump_framework.id
    assert bumps[1]["id"] == bump_framework2.id


@use_app_context
def test_create_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    archetype_2 = basic_archetype(client, sdr)

    create_bump_framework(
        client_sdr_id=sdr.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        client_archetype_ids=[],
        active=True,
        default=True
    )
    assert BumpFramework.query.count() == 1
    bump_framework: BumpFramework = BumpFramework.query.filter_by(
        client_sdr_id=sdr.id
    ).first()
    assert bump_framework.title == "title"
    assert bump_framework.description == "description"
    assert bump_framework.overall_status == ProspectOverallStatus.ACTIVE_CONVO
    assert bump_framework.bump_length.value == "LONG"
    assert bump_framework.active == True
    assert bump_framework.default == True
    assert JunctionBumpFrameworkClientArchetype.query.count() == 2

    create_bump_framework(
        client_sdr_id=sdr.id,
        title="title 2",
        description="description 2",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        client_archetype_ids=[archetype.id],
        active=True,
        default=False
    )
    assert BumpFramework.query.count() == 2
    assert JunctionBumpFrameworkClientArchetype.query.count() == 3


@use_app_context
def test_modify_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    bump_framework = basic_bump_framework(sdr, active=True)

    assert bump_framework.bump_length.value == "MEDIUM"
    modify_bump_framework(
        client_sdr_id=sdr.id,
        bump_framework_id=bump_framework.id,
        overall_status=ProspectOverallStatus.PROSPECTED,
        length=BumpLength.SHORT,
        title="new title",
        description="new description",
        default=True,
    )
    bump_framework: BumpFramework = BumpFramework.query.filter_by(
        client_sdr_id=sdr.id
    ).first()
    assert bump_framework.title == "new title"
    assert bump_framework.description == "new description"
    assert bump_framework.default == True
    assert bump_framework.bump_length.value == "SHORT"


@use_app_context
def test_deactivate_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    bump_framework = basic_bump_framework(sdr, active=True)

    deactivate_bump_framework(sdr.id, bump_framework.id)
    bump_framework: BumpFramework = BumpFramework.query.filter_by(
        client_sdr_id=sdr.id
    ).first()
    assert bump_framework.active == False


@use_app_context
def test_activate_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    bump_framework = basic_bump_framework(sdr, active=False)

    activate_bump_framework(sdr.id, bump_framework.id)
    bump_framework: BumpFramework = BumpFramework.query.filter_by(
        client_sdr_id=sdr.id
    ).first()
    assert bump_framework.active == True
