from src.research.linkedin.services import *
from decorators import use_app_context
from app import app
from test_utils import (
    test_app,
    basic_prospect,
    basic_client,
    basic_archetype,
    basic_generated_message,
    basic_gnlp_model,
    basic_research_payload,
    basic_research_point,
)
from model_import import Prospect, ResearchPayload, ResearchPoints, GeneratedMessage
import mock


@use_app_context
def test_reset_prospect_research_and_messages():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    research = basic_research_payload(prospect)
    research_point = basic_research_point(research)

    prospect.approved_outreach_message_id = generated_message_id
    db.session.add(prospect)
    db.session.commit()

    prospects: list = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].approved_outreach_message_id == generated_message_id

    research_payloads: list = ResearchPayload.query.all()
    research_points: list = ResearchPoints.query.all()
    generated_messages: list = GeneratedMessage.query.all()
    assert len(research_payloads) == 1
    assert len(research_points) == 1
    assert len(generated_messages) == 1

    reset_prospect_research_and_messages(prospect_id)

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.approved_outreach_message_id is None
    research_payloads: list = ResearchPayload.query.all()
    research_points: list = ResearchPoints.query.all()
    generated_messages: list = GeneratedMessage.query.all()
    assert len(research_payloads) == 0
    assert len(research_points) == 0
    assert len(generated_messages) == 0


@mock.patch("src.research.linkedin.services.reset_prospect_research_and_messages.delay")
def test_reset_batch_of_prospect_research_and_messages(
    reset_prospect_research_and_messages_mock,
):
    prospect_ids = [1, 2, 3, 4]
    reset_batch_of_prospect_research_and_messages(prospect_ids)

    assert reset_prospect_research_and_messages_mock.call_count == 4


@mock.patch("src.research.linkedin.services.reset_prospect_research_and_messages.delay")
def test_v1_batch_wipe_prospect_messages_and_research_endpoint(
    reset_prospect_research_and_messages_mock,
):
    response = app.test_client().delete(
        "research/v1/batch_wipe_prospect_messages_and_research",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
            }
        ),
    )
    assert response.status_code == 200
    assert reset_prospect_research_and_messages_mock.call_count == 4
