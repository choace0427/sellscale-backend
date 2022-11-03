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
from model_import import GeneratedMessageCTA, GeneratedMessage
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
