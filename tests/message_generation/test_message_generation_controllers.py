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


@mock.patch(
    "src.message_generation.services.openai.Completion.create",
    return_value={"choices": [{"text": "[Tag] This a CTA"}]},
)
def test_post_generate_ai_made_ctas(open_ai_completion_mock):
    response = app.test_client().post(
        "message_generation/generate_ai_made_ctas",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "company_name": "company name",
                "persona": "persona",
                "with_what": "with something",
            }
        ),
    )
    assert response.status_code == 200
    assert len(response.json["ctas"]) == 1
    assert open_ai_completion_mock.call_count == 1
