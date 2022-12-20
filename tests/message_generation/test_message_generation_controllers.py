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
    GeneratedMessageJobStatus,
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


@use_app_context
def test_post_clear_message_generation_jobs_queue():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client=client, archetype=archetype)
    for i in range(10):
        generated_message_job = GeneratedMessageJob(
            prospect_id=prospect.id,
            batch_id="123123",
            status=GeneratedMessageJobStatus.PENDING,
        )
        db.session.add(generated_message_job)
        db.session.commit()

    gm_jobs = GeneratedMessageJob.query.all()
    assert len(gm_jobs) == 10

    response = app.test_client().post(
        "message_generation/clear_message_generation_jobs_queue",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    gm_jobs = GeneratedMessageJob.query.all()
    assert len(gm_jobs) == 0


@use_app_context
def test_post_clear_all_good_messages_by_archetype_id():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client=client, archetype=archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    generated_message.good_message = True
    db.session.add(generated_message)
    db.session.commit()

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].good_message == True

    response = app.test_client().post(
        "message_generation/clear_all_good_messages_by_archetype_id",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "archetype_id": archetype.id,
            }
        ),
    )
    assert response.status_code == 200

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].good_message == None
