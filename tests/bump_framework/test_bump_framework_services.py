from app import db, app
from src.bump_framework.models import BumpLength
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_bump_framework,
)
from decorators import use_app_context
from src.bump_framework.services import (
    clone_bump_framework,
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
        client_archetype_id=archetype.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=True,
        default=True
    )
    bump2_id = create_bump_framework(
        client_sdr_id=sdr.id,
        client_archetype_id=archetype.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=False,
        default=True
    )
    bump_framework = BumpFramework.query.get(bump_id)
    bump_framework2 = BumpFramework.query.get(bump2_id)

    bumps = get_bump_frameworks_for_sdr(
        sdr.id, [bump_framework.overall_status])
    assert len(bumps) == 1
    assert bumps[0]["id"] == bump_framework.id

    bumps = get_bump_frameworks_for_sdr(
        sdr.id, [bump_framework.overall_status], active_only=False
    )
    assert len(bumps) == 2
    assert bumps[0]["id"] == bump_framework.id
    assert bumps[1]["id"] == bump_framework2.id

    bump3_id = create_bump_framework(
        client_sdr_id=sdr.id,
        client_archetype_id=archetype.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=True,
        substatus="ACTIVE_CONVO_OBJECTION",
        default=True
    )
    bump_framework3 = BumpFramework.query.get(bump3_id)
    bumps = get_bump_frameworks_for_sdr(
        sdr.id,
        [bump_framework.overall_status],
        ["ACTIVE_CONVO_OBJECTION"],
        active_only=False
    )
    assert len(bumps) == 1
    assert bumps[0]["id"] == bump_framework3.id


@use_app_context
def test_get_bump_frameworks_for_sdr_complex():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    bump_id = create_bump_framework(
        client_sdr_id=sdr.id,
        client_archetype_id=archetype.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=True,
        default=True
    )
    bump2_id = create_bump_framework(
        client_sdr_id=sdr.id,
        client_archetype_id=archetype.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=False,
        default=True
    )
    bump_framework = BumpFramework.query.get(bump_id)
    bump_framework2 = BumpFramework.query.get(bump2_id)

    bumps = get_bump_frameworks_for_sdr(
        client_sdr_id=sdr.id,
        exclude_client_archetype_ids=[archetype.id],
    )
    assert len(bumps) == 0

    bumps = get_bump_frameworks_for_sdr(
        client_sdr_id=sdr.id,
        unique_only=True,
    )
    assert len(bumps) == 1


@use_app_context
def test_create_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    archetype_2 = basic_archetype(client, sdr)

    create_bump_framework(
        client_sdr_id=sdr.id,
        client_archetype_id=archetype.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
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

    create_bump_framework(
        client_sdr_id=sdr.id,
        client_archetype_id=archetype.id,
        title="title 2",
        description="description 2",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=True,
        default=False
    )
    assert BumpFramework.query.count() == 2


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
        client_archetype_id=archetype_id,
        title="new title",
        description="new description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=True,
        default=False
    )
    bump_framework = BumpFramework.query.get(bump_id)

    assert bump_framework.bump_length.value == "LONG"
    modify_bump_framework(
        client_sdr_id=sdr.id,
        client_archetype_id=archetype_id,
        bump_framework_id=bump_id,
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


@use_app_context
def test_clone_bump_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    bump_framework = basic_bump_framework(sdr, archetype)
    assert BumpFramework.query.count() == 1

    archetype_2 = basic_archetype(client, sdr)
    bump_framework_2_id = clone_bump_framework(sdr.id, bump_framework.id, archetype_2.id)
    assert BumpFramework.query.count() == 2
    bump_framework_2: BumpFramework = BumpFramework.query.get(bump_framework_2_id)
    assert bump_framework_2.client_sdr_id == archetype_2.client_sdr_id
    assert bump_framework_2.client_archetype_id == archetype_2.id
    assert bump_framework_2.title == bump_framework.title
    assert bump_framework_2.description == bump_framework.description
    assert bump_framework_2.overall_status == bump_framework.overall_status
    assert bump_framework_2.bump_length == bump_framework.bump_length
    assert bump_framework_2.active == bump_framework.active
    assert bump_framework_2.default == True
    assert bump_framework_2.sellscale_default_generated == False
