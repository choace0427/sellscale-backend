from app import db
from test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_generated_message,
    basic_gnlp_model,
    basic_prospect,
)
from decorators import use_app_context
from src.message_generation.services import *
from model_import import GeneratedMessageCTA, GeneratedMessage, GeneratedMessageStatus
from src.research.models import ResearchPointType, ResearchType
from src.client.services import create_client
from model_import import Client
from app import db
import mock


@use_app_context
def test_create_cta():
    client = basic_client()
    archetype = basic_archetype(client)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    assert cta.text_value == "test"
    assert cta.archetype_id == archetype.id


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

    assert cta.active == None
    toggle_cta_active(cta_id=cta.id)
    assert cta.active == True
    toggle_cta_active(cta_id=cta.id)
    assert cta.active == False


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
