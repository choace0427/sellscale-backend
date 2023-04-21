from app import db, app
from src.research.models import (
    AccountResearchPoints,
    ResearchPointType,
    AccountResearchType,
)
from decorators import use_app_context
from src.message_generation.services import *
from app import db
import mock
import json
from test_utils import test_app
from test_utils import basic_client, basic_archetype, basic_prospect, basic_client_sdr


@use_app_context
def test_get_all_research_point_types():
    """Assert that everything returned from GET /research/all_research_point_types_details
    appears in ResearchPointType enum. Every value in get_all_research_point_types
    will look like:

    {
        "transformer": ResearchPointType.CURRENT_JOB_SPECIALTIES.value,
        "description": "Extracts the specialties of the current job",
        "example": "Filene Research Institute is a research, innovation, applied services, and credit unions",
        "deprecated": False,
    }"""
    response = app.test_client().get(
        "research/all_research_point_types_details",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    all_research_point_types = response.json or []

    for research_point_type in all_research_point_types:
        assert (
            research_point_type["transformer"] in ResearchPointType.__members__.keys()
        )
        assert research_point_type["description"] is not None
        assert research_point_type["example"] is not None
        assert research_point_type["deprecated"] is not None

    assert len(all_research_point_types) == len(ResearchPointType.__members__.keys())


@use_app_context
def test_get_account_research_points():
    """Assert that the research points returned from GET /research/account_research_points
    are the same as the ones returned from the database."""
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(
        client=client,
        archetype=archetype,
        client_sdr=client_sdr,
    )
    prospect_id = prospect.id

    response = app.test_client().get(
        f"research/account_research_points?prospect_id={prospect.id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + "TEST_AUTH_TOKEN",
        },
    )
    assert response.status_code == 200
    research_points = response.json or []

    account_research_point = AccountResearchPoints(
        prospect_id=prospect_id,
        account_research_type=AccountResearchType.GENERIC_RESEARCH,
        title="test title",
        reason="test reason",
    )
    db.session.add(account_research_point)
    db.session.commit()

    response = app.test_client().get(
        f"research/account_research_points?prospect_id={prospect.id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + "TEST_AUTH_TOKEN",
        },
    )
    assert response.status_code == 200

    research_points = response.json or []
    assert len(research_points) == 1
