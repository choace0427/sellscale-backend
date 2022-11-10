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
)
from decorators import use_app_context
from src.message_generation.services import *
from model_import import GeneratedMessageCTA, GeneratedMessage, GeneratedMessageStatus
from src.research.models import ResearchPointType, ResearchType
from src.client.services import create_client
from model_import import Client, ProspectStatus
from app import db
import mock
import json


@use_app_context
def test_create_cta():
    client = basic_client()
    archetype = basic_archetype(client)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    assert cta.text_value == "test"
    assert cta.archetype_id == archetype.id
    assert cta.active


@use_app_context
def test_delete_cta():
    client = basic_client()
    archetype = basic_archetype(client)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    all_ctas: list = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 1

    success = delete_cta(cta_id=cta.id)
    all_ctas = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 0


@use_app_context
def test_toggle_cta():
    client = basic_client()
    archetype = basic_archetype(client)
    cta = create_cta(text_value="test", archetype_id=archetype.id)

    assert cta.active == True
    toggle_cta_active(cta_id=cta.id)
    assert cta.active == False
    toggle_cta_active(cta_id=cta.id)
    assert cta.active == True


@use_app_context
def test_delete_cta_with_generated_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    all_ctas: list = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 1

    message: GeneratedMessage = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    message.message_cta = cta.id
    db.session.add(message)
    db.session.commit()

    success = delete_cta(cta_id=cta.id)
    assert success is False
    all_ctas = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 1


@use_app_context
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch(
    "src.message_generation.services.generate_few_shot_generation_prompt",
    return_value=["test", []],
)
@mock.patch(
    "src.message_generation.services.get_basic_openai_completion",
    return_value=["completion 1", "completion 2"],
)
def test_few_shot_generations(openai_patch, prompt_patch, bullets_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    gnlp_model.id = 5
    db.session.add(gnlp_model)
    db.session.commit()

    prospect = basic_prospect(client, archetype)
    example_ids = []
    cta_prompt = "This is a prompt CTA."

    success = few_shot_generations(
        prospect_id=prospect.id, example_ids=example_ids, cta_prompt=cta_prompt
    )
    assert success is True
    assert openai_patch.called is True
    assert prompt_patch.called is True
    assert bullets_patch.called is True

    gm_list: list = GeneratedMessage.query.all()
    assert len(gm_list) == 2
    for gm in gm_list:
        assert gm.message_type == GeneratedMessageType.LINKEDIN


@use_app_context
@mock.patch(
    "src.message_generation.services.get_custom_completion_for_client",
    return_value=[["completion 1", "completion 2"], 5],
)
@mock.patch(
    "src.message_generation.services.get_adversarial_ai_approval", return_value=True
)
def test_generate_outreaches_new(ai_patch, completion_patch):
    payload = create_client(company="test", contact_name="test", contact_email="test")
    client: Client = Client.query.get(payload["client_id"])
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    gnlp_model = basic_gnlp_model(archetype)
    gnlp_model.id = 5
    db.session.add(gnlp_model)
    db.session.commit()

    research_payload: ResearchPayload = ResearchPayload(
        prospect_id=prospect.id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(research_payload)
    db.session.commit()

    for i in ["research 1", "research 2"]:
        rp: ResearchPoints = ResearchPoints(
            research_payload_id=research_payload.id,
            research_point_type=ResearchPointType.GENERAL_WEBSITE_TRANSFORMER,
            value=i,
        )
        db.session.add(rp)
        db.session.commit()

    outreaches = generate_outreaches_new(
        prospect_id=prospect.id,
        batch_id="123123123",
        cta_id=cta.id,
    )
    assert len(outreaches) == 8
    assert ai_patch.called is True
    assert completion_patch.called is True

    generated_messages: list = GeneratedMessage.query.all()
    assert len(generated_messages) == 8
    for gm in generated_messages:
        assert gm.message_type == GeneratedMessageType.LINKEDIN
        assert gm.message_cta == cta.id
        assert gm.batch_id == "123123123"


@use_app_context
def test_update_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    message: GeneratedMessage = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    db.session.add(message)
    db.session.commit()

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message.completion == "this is a test"
    assert not message.human_edited

    success = update_message(message_id=message.id, update="this is an update copy")
    assert success is True
    messages: GeneratedMessage = GeneratedMessage.query.all()
    assert len(messages) == 1

    message = messages[0]
    assert message.completion == "this is an update copy"
    assert message.human_edited == True


@mock.patch("src.message_generation.controllers.update_message")
def test_batch_update_messages(update_message_mock):
    response = app.test_client().patch(
        "/message_generation/batch_update",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "linkedin_url": "linkedin.com/in/jameszw",
                        "id": 102,
                        "full_name": "Test 2",
                        "title": "VP of Sales Ops & Strategy at Velocity Global",
                        "company": "Velocity Global",
                        "completion": "This is a test 1\n",
                        "message_id": 2,
                    },
                    {
                        "linkedin_url": "linkedin.com/in/jameszw",
                        "id": 2028,
                        "full_name": "Test 1",
                        "title": "VP of Sales Ops & Strategy at Velocity Global",
                        "company": "Velocity Global",
                        "completion": "This is a test 1\n",
                        "message_id": 3,
                    },
                ]
            }
        ),
    )
    assert response.status_code == 200
    assert update_message_mock.call_count == 2


@use_app_context
def test_approve_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    message: GeneratedMessage = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    db.session.add(message)
    db.session.commit()

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message.message_status == GeneratedMessageStatus.DRAFT

    approve_message(message_id=message.id)

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message.message_status == GeneratedMessageStatus.APPROVED


@use_app_context
def test_delete_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    message: GeneratedMessage = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    db.session.add(message)
    db.session.commit()

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message.message_status == GeneratedMessageStatus.DRAFT

    delete_message(message_id=message.id)

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message == None


@use_app_context
def test_delete_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    for i in range(10):
        basic_generated_message(prospect=prospect, gnlp_model=gnlp_model)

    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 10

    delete_message_generation_by_prospect_id(prospect_id=prospect.id)

    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 0


@use_app_context
@mock.patch(
    "src.message_generation.services.get_custom_completion_for_client",
    return_value=("completion", 5),
)
def test_generate_prospect_email(get_custom_completion_for_client_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    gnlp_model = basic_gnlp_model(archetype)
    gnlp_model.id = 5
    db.session.add(gnlp_model)
    db.session.commit()
    email_schema = basic_email_schema(archetype)
    email_schema_id = email_schema.id

    generate_prospect_email(
        prospect_id=prospect.id, email_schema_id=email_schema.id, batch_id="123123"
    )

    assert get_custom_completion_for_client_mock.called is True

    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 3
    for message in messages:
        assert message.message_type == GeneratedMessageType.EMAIL
        assert message.gnlp_model_id == 5
        assert message.completion == "completion"
        assert message.batch_id == "123123"

    prospect_emails: list = ProspectEmail.query.all()
    assert len(prospect_emails) == 3
    for prospect_email in prospect_emails:
        assert prospect_email.prospect_id == prospect_id
        assert prospect_email.email_schema_id == email_schema_id
        assert prospect_email.personalized_first_line in [x.id for x in messages]
        assert prospect_email.batch_id == "123123"


@use_app_context
@mock.patch(
    "src.message_generation.services.get_custom_completion_for_client",
    return_value=("completion", 5),
)
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
def test_research_and_generate_emails_for_prospect_and_wipe(
    linkedin_research_patch, get_custom_completion_for_client_mock
):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    gnlp_model = basic_gnlp_model(archetype)
    gnlp_model.id = 5
    gnlp_model_id = 5
    db.session.add(gnlp_model)
    db.session.commit()
    email_schema = basic_email_schema(archetype)
    email_schema_id = email_schema.id

    rp: ResearchPayload = ResearchPayload(
        prospect_id=prospect_id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(rp)
    db.session.commit()

    generate_prospect_email(
        prospect_id=prospect.id, email_schema_id=email_schema.id, batch_id="123123"
    )

    assert get_custom_completion_for_client_mock.called is True

    messages: list = GeneratedMessage.query.all()
    batch_id = messages[0].batch_id
    assert len(messages) == 3
    for message in messages:
        assert message.message_type == GeneratedMessageType.EMAIL
        assert message.gnlp_model_id == 5
        assert message.completion == "completion"
        assert message.batch_id == "123123"

    prospect_emails: list = ProspectEmail.query.all()
    assert len(prospect_emails) == 3
    for prospect_email in prospect_emails:
        assert prospect_email.prospect_id == prospect_id
        assert prospect_email.email_schema_id == email_schema_id
        assert prospect_email.personalized_first_line in [x.id for x in messages]
        assert prospect_email.batch_id == "123123"

    another_client = basic_client()
    another_archetype = basic_archetype(another_client)
    another_prospect = basic_prospect(another_client, another_archetype)
    another_prospect_id = another_prospect.id

    rp: ResearchPayload = ResearchPayload(
        prospect_id=another_prospect_id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(rp)
    db.session.commit()

    generate_prospect_email(
        prospect_id=another_prospect_id,
        email_schema_id=email_schema_id,
        batch_id="123123",
    )

    messages: list = GeneratedMessage.query.all()
    prospect_emails = ProspectEmail.query.all()
    assert len(messages) == 6
    assert len(prospect_emails) == 6

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.status = ProspectStatus.PROSPECTED
    db.session.add(prospect)
    db.session.commit()

    wipe_prospect_email_and_generations_and_research(prospect_id=prospect_id)
    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 3
    prospect_emails = ProspectEmail.query.all()
    assert len(prospect_emails) == 3
    for email in prospect_emails:
        assert email.prospect_id == another_prospect_id


@use_app_context
@mock.patch(
    "src.message_generation.services.get_custom_completion_for_client",
    return_value=("completion", 5),
)
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch("src.message_generation.services.generate_prospect_email.delay")
def test_batch_generate_emails_for_prospect(
    generate_email_mock, linkedin_research_patch, get_custom_completion_for_client_mock
):
    client = basic_client()
    archetype = basic_archetype(client)
    email_schema = basic_email_schema(archetype)

    batch_generate_prospect_emails(
        prospect_ids=[1, 2, 3],
        email_schema_id=email_schema.id,
    )
    assert generate_email_mock.call_count == 3


@use_app_context
@mock.patch(
    "src.message_generation.services.get_custom_completion_for_client",
    return_value=("completion", 5),
)
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch(
    "src.message_generation.services.research_and_generate_outreaches_for_prospect.delay"
)
def test_research_and_generate_outreaches_for_prospect_list(
    generate_outreach_mock,
    linkedin_research_patch,
    get_custom_completion_for_client_mock,
):
    client = basic_client()
    archetype = basic_archetype(client)
    email_schema = basic_email_schema(archetype)

    research_and_generate_outreaches_for_prospect_list(
        prospect_ids=[1, 2, 3],
    )
    assert generate_outreach_mock.call_count == 3


@use_app_context
def test_change_prospect_email_status():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    email_schema = basic_email_schema(archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    prospect_email: ProspectEmail = basic_prospect_email(prospect, email_schema)
    prospect_email.personalized_first_line = generated_message_id
    db.session.add(prospect_email)
    db.session.commit()

    prospect_email = ProspectEmail.query.get(prospect_email.id)
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT
    assert prospect_email.personalized_first_line == generated_message_id
    assert generated_message.message_status == GeneratedMessageStatus.DRAFT

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == None

    mark_prospect_email_approved(prospect_email.id)

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email.id)
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.APPROVED
    assert generated_message.message_status == GeneratedMessageStatus.APPROVED

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == prospect_email.id

    mark_prospect_email_sent(prospect_email.id)
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.SENT
    assert generated_message.message_status == GeneratedMessageStatus.SENT


def test_prospect_email_status_and_generated_message_status_parity():
    gm_status = [x.value for x in GeneratedMessageStatus]
    pe_status = [x.value for x in ProspectEmailStatus]

    assert len(gm_status) == len(pe_status)
    for status in gm_status:
        assert status in pe_status
    for status in pe_status:
        assert status in gm_status


@use_app_context
def test_change_prospect_email_status():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    email_schema = basic_email_schema(archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    prospect_email: ProspectEmail = basic_prospect_email(prospect, email_schema)
    prospect_email.personalized_first_line = generated_message_id
    db.session.add(prospect_email)
    db.session.commit()

    prospect_email = ProspectEmail.query.get(prospect_email.id)
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT
    assert prospect_email.personalized_first_line == generated_message_id
    assert generated_message.message_status == GeneratedMessageStatus.DRAFT

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == None

    mark_prospect_email_approved(prospect_email.id)

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email.id)
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.APPROVED
    assert generated_message.message_status == GeneratedMessageStatus.APPROVED

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == prospect_email.id

    response = app.test_client().post(
        "email_generation/batch/mark_sent",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [prospect.id],
            }
        ),
    )

    assert response.status_code == 200

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.status == ProspectStatus.SENT_OUTREACH

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email.id)
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.SENT
    assert generated_message.message_status == GeneratedMessageStatus.SENT


@use_app_context
def test_batch_approve_message_generations_by_heuristic():
    prospect_ids = []

    client = basic_client()
    archetype = basic_archetype(client)
    for i in range(10):
        prospect = basic_prospect(client, archetype)
        prospect_ids.append(prospect.id)
        gnlp_model = basic_gnlp_model(archetype)
        message: GeneratedMessage = basic_generated_message(
            prospect=prospect, gnlp_model=gnlp_model
        )
        db.session.add(message)
        db.session.commit()

    messages: GeneratedMessage = GeneratedMessage.query.all()
    assert len(messages) == 10
    for message in messages:
        assert message.message_status == GeneratedMessageStatus.DRAFT
        prospect: Prospect = Prospect.query.get(message.prospect_id)
        assert prospect.approved_prospect_email_id == None
        assert prospect.status == ProspectStatus.PROSPECTED

    # batch_approve_message_generations_by_heuristic(prospect_ids=prospect_ids)
    response = app.test_client().post(
        "/message_generation/batch_approve",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": prospect_ids,
            }
        ),
    )
    assert response.status_code == 200

    messages: GeneratedMessage = GeneratedMessage.query.all()
    assert len(messages) == 10
    for message in messages:
        assert message.message_status == GeneratedMessageStatus.APPROVED
        prospect: Prospect = Prospect.query.get(message.prospect_id)
        assert prospect.status == ProspectStatus.PROSPECTED
