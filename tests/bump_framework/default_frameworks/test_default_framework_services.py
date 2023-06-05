from app import db, app
from src.bump_framework.default_frameworks.services import (
    create_default_bump_frameworks,
    add_archetype_to_default_bump_frameworks,
)
from src.bump_framework.models import JunctionBumpFrameworkClientArchetype
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
)
from decorators import use_app_context
from model_import import BumpFramework

@use_app_context
def test_create_default_bump_frameworks():
    client = basic_client()
    sdr = basic_client_sdr(client)

    count = create_default_bump_frameworks(sdr.id)
    assert count == 6
    assert BumpFramework.query.count() == 6
    assert JunctionBumpFrameworkClientArchetype.query.count() == 0 # No archetypes, so no junctions.


@use_app_context
def test_add_archetype_to_default_bump_frameworks():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)

    count = create_default_bump_frameworks(sdr.id)
    assert count == 6
    assert BumpFramework.query.count() == 6
    assert JunctionBumpFrameworkClientArchetype.query.count() == 6

    archetype2 = basic_archetype(client, sdr)
    add_archetype_to_default_bump_frameworks(sdr.id, archetype2.id)
    assert BumpFramework.query.count() == 6
    assert JunctionBumpFrameworkClientArchetype.query.count() == 12
