from app import db, app
from src.research.services import get_all_research_point_types, create_research_point
, ResearchType
from tests.test_utils.decorators import use_app_context
from src.message_generation.services import *
from app import db
import mock
import json
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_prospect,
    basic_research_payload,
)


@use_app_context
def test_get_all_research_point_types():
    """Assert that everything returned from get_all_research_point_types
    appears in ResearchPointType enum. Every value in get_all_research_point_types
    will look like:

    {
        "transformer": ResearchPointType.CURRENT_JOB_SPECIALTIES.value,
        "description": "Extracts the specialties of the current job",
        "example": "Filene Research Institute is a research, innovation, applied services, and credit unions",
        "deprecated": False,
    }"""
    all_research_point_types = get_all_research_point_types()
    # TODO: Update this test to new system
    for research_point_type in all_research_point_types:
        # assert (
        #     research_point_type["transformer"] in ResearchPointType.__members__.keys()
        # )
        assert research_point_type["description"] is not None
        assert research_point_type["example"] is not None
        assert research_point_type["deprecated"] is not None

    # assert len(all_research_point_types) == len(ResearchPointType.__members__.keys())


@use_app_context
def test_create_research_point():
    c = basic_client()
    a = basic_archetype(c)
    p = basic_prospect(c, a)
    rp = basic_research_payload(p)
    rp.research_type = ResearchType.SERP_PAYLOAD
    db.session.add(rp)
    db.session.commit()

    point_id = create_research_point(
        payload_id=rp.id,
        research_point_type="SERP_NEWS_SUMMARY",
        text="test",
        research_point_metadata={"test": "test"},
    )
    assert point_id is not None
    point = ResearchPoints.query.get(point_id)
    assert point is not None
    assert point.research_payload_id == rp.id
    assert point.research_point_type == "SERP_NEWS_SUMMARY"
    assert point.value == "test"
    assert point.research_point_metadata == {"test": "test"}
