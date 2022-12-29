from app import db, app
from src.research.services import get_all_research_point_types
from src.research.models import ResearchPointType
from decorators import use_app_context
from src.message_generation.services import *
from app import db
import mock
import json
from test_utils import test_app


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
    for research_point_type in all_research_point_types:
        assert (
            research_point_type["transformer"] in ResearchPointType.__members__.keys()
        )
        assert research_point_type["description"] is not None
        assert research_point_type["example"] is not None
        assert research_point_type["deprecated"] is not None

    assert len(all_research_point_types) == len(ResearchPointType.__members__.keys())
