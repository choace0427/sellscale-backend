from src.research.linkedin.services import *
from tests.test_utils.decorators import use_app_context
from app import app
from tests.test_utils.test_utils import (
    test_app,
    basic_prospect,
    basic_client,
    basic_archetype,
    basic_generated_message,
    basic_research_payload,
    basic_research_point,
)
from model_import import Prospect, ResearchPayload, ResearchPoints, GeneratedMessage
import mock


@use_app_context
def test_post_flag_research_point():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    research_payload = basic_research_payload(prospect)
    research_point = basic_research_point(research_payload)
    research_point_id = research_point.id

    response = app.test_client().post(
        "research/v1/flag_research_point",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "research_point_id": research_point_id,
            }
        ),
    )
    assert response.status_code == 200

    research_point: ResearchPoints = ResearchPoints.query.get(research_point_id)
    assert research_point is not None
    assert research_point.flagged is True
