from src.research.linkedin.services import *
from tests.test_utils.decorators import use_app_context
from app import app
from tests.test_utils.test_utils import (
    test_app,
    basic_prospect,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_generated_message,
    basic_research_payload,
    basic_research_point,
)
from model_import import Prospect, ResearchPayload, ResearchPoints, GeneratedMessage
import mock
import json
from src.research.account_research import (
    generate_research,
    get_research_paragraph_form,
    get_research_bullet_form,
    get_research_json,
)

MOCK_GET_RESEARCH_PARAGRAPH_FORM = (
    [
        {"role": "user", "content": "Give me a research paragraph."},
        {"role": "assistant", "content": "Here is a research paragraph."},
    ],
    "Here is a research paragraph.",
)

MOCK_GET_RESEARCH_BULLET_FORM = (
    [
        {"role": "user", "content": "Give me a research paragraph."},
        {"role": "assistant", "content": "Here is a research paragraph."},
        {"role": "user", "content": "Turn into research bullet."},
        {"role": "assistant", "content": "Here is a research bullet."},
    ],
    "Here is a research bullet.",
)

MOCK_GET_RESEARCH_JSON = (
    [
        {"role": "user", "content": "Give me a research paragraph."},
        {"role": "assistant", "content": "Here is a research paragraph."},
        {"role": "user", "content": "Turn into research bullet."},
        {"role": "assistant", "content": "Here is a research bullet."},
        {"role": "user", "content": "Turn into research json."},
        {"role": "assistant", "content": json.dumps({"key": "value"})},
    ],
    json.dumps({"key": "value"}),
)


@use_app_context
@mock.patch(
    "src.research.account_research.get_research_paragraph_form",
    return_value=MOCK_GET_RESEARCH_PARAGRAPH_FORM,
)
@mock.patch(
    "src.research.account_research.get_research_bullet_form",
    return_value=MOCK_GET_RESEARCH_BULLET_FORM,
)
@mock.patch(
    "src.research.account_research.get_research_json",
    return_value=MOCK_GET_RESEARCH_JSON,
)
def test_generate_research(mock_json, mock_bullet, mock_paragraph):
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)

    success, research = generate_research(prospect.id, 3)
    assert success
    assert research.get("key") == "value"
    assert mock_json.call_count == 1
    assert mock_json.called_with(prospect.id, MOCK_GET_RESEARCH_BULLET_FORM[0])
    assert mock_bullet.call_count == 1
    assert mock_bullet.called_with(prospect.id, MOCK_GET_RESEARCH_PARAGRAPH_FORM[0])
    assert mock_paragraph.call_count == 1
    assert mock_paragraph.called_with(prospect.id)


@use_app_context
@mock.patch(
    "src.research.account_research.wrapped_chat_gpt_completion_with_history",
    return_value=MOCK_GET_RESEARCH_PARAGRAPH_FORM,
)
@mock.patch(
    "src.research.linkedin.services.get_research_payload_new",
    return_value={
        "company": {
            "details": {
                "tagline": "test tagline",
                "description": "test description",
                "staff": {"total": 100},
            }
        }
    },
)
def test_get_research_paragraph_form(mock_payload, mock_chatgpt):
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)

    history, completion = get_research_paragraph_form(prospect.id)
    assert history == MOCK_GET_RESEARCH_PARAGRAPH_FORM[0]
    assert completion == MOCK_GET_RESEARCH_PARAGRAPH_FORM[1]
    assert mock_payload.call_count == 1
    assert mock_payload.called_with(prospect.id)
    assert mock_chatgpt.call_count == 1
