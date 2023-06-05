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
    archetype = basic_archetype(client, sdr)
    bump_id = create_bump_framework(
        client_sdr_id=sdr.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        client_archetype_ids=[archetype.id],
        active=True,
        default=True
    )
    bump2_id = create_bump_framework(
        client_sdr_id=sdr.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        client_archetype_ids=[archetype.id],
        active=False,
        default=True
    )
    bump_framework = BumpFramework.query.get(bump_id)
    bump_framework2 = BumpFramework.query.get(bump2_id)

    bumps = get_bump_frameworks_for_sdr(sdr.id, [bump_framework.overall_status])
    assert len(bumps) == 1
    assert bumps[0]["id"] == bump_framework.id

    bumps = get_bump_frameworks_for_sdr(
        sdr.id, [bump_framework.overall_status], activeOnly=False
    )
    assert len(bumps) == 2
    assert bumps[0]["id"] == bump_framework.id
    assert bumps[1]["id"] == bump_framework2.id

    bump3_id = create_bump_framework(
        client_sdr_id=sdr.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        client_archetype_ids=[archetype.id],
        active=True,
        substatus="ACTIVE_CONVO_OBJECTION",
        default=True
    )
    bump_framework3 = BumpFramework.query.get(bump3_id)
    bumps = get_bump_frameworks_for_sdr(
        sdr.id,
        [bump_framework.overall_status],
        ["ACTIVE_CONVO_OBJECTION"],
        activeOnly=False
    )
    assert len(bumps) == 1
    assert bumps[0]["id"] == bump_framework3.id



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
    archetype = basic_archetype(client, sdr)
    archetype2 = basic_archetype(client, sdr)
    archetype3 = basic_archetype(client, sdr)
    archetype_id = archetype.id
    archetype2_id = archetype2.id
    archetype3_id = archetype3.id

    bump_id = create_bump_framework(
        client_sdr_id=sdr.id,
        title="new title",
        description="new description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        client_archetype_ids=[archetype_id],
        active=True,
        default=False
    )
    junctions = JunctionBumpFrameworkClientArchetype.query.count()
    assert junctions == 1
    bump_framework = BumpFramework.query.get(bump_id)

    assert bump_framework.bump_length.value == "LONG"
    modify_bump_framework(
        client_sdr_id=sdr.id,
        bump_framework_id=bump_id,
        overall_status=ProspectOverallStatus.PROSPECTED,
        length=BumpLength.SHORT,
        client_archetype_ids=[archetype_id, archetype2_id],
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
    junctions = JunctionBumpFrameworkClientArchetype.query.count()
    assert junctions == 2

    # Test duplicate removal on client_archetype_ids
    modify_bump_framework(
        client_sdr_id=sdr.id,
        bump_framework_id=bump_id,
        overall_status=ProspectOverallStatus.PROSPECTED,
        length=BumpLength.SHORT,
        client_archetype_ids=[archetype3_id, archetype3_id],
        title="new title",
        description="new description",
        default=True,
    )
    junctions = JunctionBumpFrameworkClientArchetype.query.count()
    assert junctions == 1

    # Test delete all junctions
    modify_bump_framework(
        client_sdr_id=sdr.id,
        bump_framework_id=bump_framework.id,
        overall_status=ProspectOverallStatus.PROSPECTED,
        length=BumpLength.SHORT,
        client_archetype_ids=[],
        title="new title",
        description="new description",
        default=True,
    )
    junctions = JunctionBumpFrameworkClientArchetype.query.count()
    assert junctions == 0


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
