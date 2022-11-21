from app import db, app
from test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_generated_message,
    basic_gnlp_model,
    basic_prospect,
    basic_email_schema,
    basic_prospect_email,
    basic_research_payload,
    basic_research_point,
)
from decorators import use_app_context
from src.message_generation.services import *
from model_import import (
    GeneratedMessageCTA,
    GeneratedMessage,
    GeneratedMessageStatus,
    GeneratedMessageFeedback,
)
from src.research.models import ResearchPointType, ResearchType
from src.client.services import create_client
from model_import import Client, ProspectStatus
from app import db
import mock
import json


@use_app_context
def test_create_feedback():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    message_id = generated_message.id

    response = app.test_client().post(
        "message_generation/add_feedback",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_id": message_id,
                "feedback_value": "this is a test",
            }
        ),
    )
    assert response.status_code == 200

    feedbacks: list = GeneratedMessageFeedback.query.all()
    assert len(feedbacks) == 1
    feedback: GeneratedMessageFeedback = feedbacks[0]
    assert feedback.feedback_value == "this is a test"
