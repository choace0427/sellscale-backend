from app import db, app
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_generated_message,
    basic_outbound_campaign,
    basic_prospect,
    basic_generated_message_cta,
)
from tests.test_utils.decorators import use_app_context
from src.message_generation.services import *
from model_import import (
    GeneratedMessageCTA,
    GeneratedMessage,
    GeneratedMessageStatus,
    GeneratedMessageFeedback,
    GeneratedMessageJobStatus,
    StackRankedMessageGenerationConfiguration,
)
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
    generated_message = basic_generated_message(prospect)
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
    generated_message = basic_generated_message(prospect=prospect)
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


@use_app_context
def test_post_toggle_message_as_good_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client=client, archetype=archetype)

    generated_message = basic_generated_message(prospect=prospect)
    generated_message.good_message = None
    db.session.add(generated_message)
    db.session.commit()

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].good_message == None

    response = app.test_client().post(
        "message_generation/toggle_message_as_good_message",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_id": generated_message.id,
            }
        ),
    )
    assert response.status_code == 200

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].good_message == True


@use_app_context
def test_post_mark_messages_as_good_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client=client, archetype=archetype)

    generated_message = basic_generated_message(prospect=prospect)
    generated_message.good_message = None
    db.session.add(generated_message)
    db.session.commit()

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].good_message == None

    response = app.test_client().post(
        "message_generation/mark_messages_as_good_message",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_ids": [generated_message.id],
            }
        ),
    )
    assert response.status_code == 200

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].good_message == True


@use_app_context
def test_post_mass_update():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client=client, archetype=archetype)

    generated_message = basic_generated_message(prospect=prospect)
    generated_message.completion = "123123"
    db.session.add(generated_message)
    db.session.commit()
    prospect.approved_outreach_message_id = generated_message.id
    db.session.add(prospect)
    db.session.commit()

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].completion == "123123"
    assert prospect.approved_outreach_message_id == generated_message.id

    response = app.test_client().post(
        "message_generation/mass_update",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "Message": "Swag swag swag",
                        "Prospect ID": prospect.id,
                    }
                ]
            }
        ),
    )
    assert response.status_code == 200

    gm_list = GeneratedMessage.query.all()
    assert len(gm_list) == 1
    assert gm_list[0].completion == "Swag swag swag"
    assert prospect.approved_outreach_message_id == generated_message.id

    response = app.test_client().post(
        "message_generation/mass_update",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "Prospect ID": prospect.id,
                    }
                ]
            }
        ),
    )
    assert response.status_code == 400
    assert response.text == "`Message` column not in CSV"

    response = app.test_client().post(
        "message_generation/mass_update",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "Message": "Swag swag swag",
                    }
                ]
            }
        ),
    )
    assert response.status_code == 400
    assert response.text == "`Prospect ID` column not in CSV"


@use_app_context
def test_create_sample_cta_and_batch_update_ctas():
    client = basic_client()
    archetype = basic_archetype(client)
    cta = basic_generated_message_cta(archetype=archetype)
    cta2 = basic_generated_message_cta(archetype=archetype)

    response = app.test_client().post(
        "message_generation/update_ctas",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {"id": cta.id, "active": False},
                    {"id": cta2.id, "active": True},
                ]
            }
        ),
    )
    assert response.status_code == 200

    cta_list = GeneratedMessageCTA.query.all()
    assert len(cta_list) == 2

    cta1 = GeneratedMessageCTA.query.filter_by(id=cta.id).first()
    assert cta1.active == False

    cta2 = GeneratedMessageCTA.query.filter_by(id=cta2.id).first()
    assert cta2.active == True


@use_app_context
def test_post_create_and_edit_stack_ranked_configuration():
    client = basic_client()
    archetype = basic_archetype(client)

    response = app.test_client().post(
        "message_generation/create_stack_ranked_configuration",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "configuration_type": "STRICT",
                "research_point_types": [],
                "instruction": "Swag swag swag",
                "name": "Swag",
                "client_id": client.id,
                "archetype_id": archetype.id,
                "generated_message_type": "LINKEDIN",
            }
        ),
    )
    assert response.status_code == 200

    configs = StackRankedMessageGenerationConfiguration.query.all()
    assert len(configs) == 1

    config = StackRankedMessageGenerationConfiguration.query.first()
    assert config.configuration_type.value == "STRICT"
    assert config.instruction == "Swag swag swag"
    assert config.name == "Swag"
    config_id = config.id

    response = app.test_client().post(
        "message_generation/edit_stack_ranked_configuration/instruction",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "configuration_id": config_id,
                "instruction": "Swag swag swag 2",
            }
        ),
    )
    assert response.status_code == 200

    config = StackRankedMessageGenerationConfiguration.query.first()
    assert config.instruction == "Swag swag swag 2"

    response = app.test_client().post(
        "message_generation/edit_stack_ranked_configuration/research_point_types",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "configuration_id": config_id,
                "research_point_types": ["GENERAL_WEBSITE_TRANSFORMER"],
            }
        ),
    )
    assert response.status_code == 200

    config = StackRankedMessageGenerationConfiguration.query.first()
    assert config.research_point_types == ["GENERAL_WEBSITE_TRANSFORMER"]

    response = app.test_client().post(
        "message_generation/edit_stack_ranked_configuration/name",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "configuration_id": config_id,
                "name": "Swag 2",
            }
        ),
    )
    assert response.status_code == 200

    config = StackRankedMessageGenerationConfiguration.query.first()
    assert config.name == "Swag 2"

    response = app.test_client().delete(
        "message_generation/stack_ranked_configuration",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "configuration_id": config_id,
            }
        ),
    )
    assert response.status_code == 200

    configs = StackRankedMessageGenerationConfiguration.query.all()
    assert len(configs) == 0


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine", return_value=[])
def test_post_pick_new_approved_message(rule_engine_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    generated_message1 = basic_generated_message(prospect)
    gm_1_id = generated_message1.id
    generated_message2 = basic_generated_message(prospect)
    gm_2_id = generated_message2.id

    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    prospect.approved_outreach_message_id = gm_1_id
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().post(
        "message_generation/pick_new_approved_message",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id, "message_id": gm_1_id}),
    )
    assert response.status_code == 200

    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    assert prospect.approved_outreach_message_id == gm_2_id

    assert rule_engine_mock.call_count == 1


@use_app_context
def test_manual_mark_ai_approve_endpoint():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    cta = basic_generated_message_cta(archetype)
    campaign = basic_outbound_campaign(
        [prospect.id],
        GeneratedMessageType.EMAIL,
        client_archetype=archetype,
        client_sdr=sdr,
    )
    gm = basic_generated_message(prospect, cta)

    # Approve
    assert gm.ai_approved == None
    response = app.test_client().patch(
        f"message_generation/{gm.id}/patch_message_ai_approve",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"new_ai_approve_status": True}),
    )
    assert response.status_code == 200
    assert response.json["message"] == "Message marked as approved"

    # Unapprove
    assert gm.ai_approved == True
    response = app.test_client().patch(
        f"message_generation/{gm.id}/patch_message_ai_approve",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"new_ai_approve_status": False}),
    )
    assert response.status_code == 200
    assert response.json["message"] == "Message marked as unapproved"
