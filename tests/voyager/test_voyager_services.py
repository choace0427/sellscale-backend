from app import db, app
from src.voyager.services import get_prospect_status_from_convo
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_generated_message,
    basic_prospect,
)
from tests.test_utils.decorators import use_app_context
from src.message_generation.services import *
from app import db
import mock
import json
from model_import import ClientSDR


@use_app_context
@mock.patch("src.voyager.services.chat_ai_verify_scheduling_convo", return_value=True)
@mock.patch(
    "src.voyager.services.chat_ai_classify_active_convo",
    return_value=ProspectStatus.ACTIVE_CONVO_CIRCLE_BACK,
)
def test_get_prospect_status_from_convo(
    mock_chat_ai_classify_active_convo, mock_chat_ai_verify_scheduling_convo
):
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr.name = "David"

    messages = [
        "David (7/4): Hey Aakash, would you like to buy an AI solution from me",
        "Aakash (7/6): Not now, I am a bit busy",
    ]
    result = get_prospect_status_from_convo(messages, sdr.id)
    assert result == ProspectStatus.ACTIVE_CONVO_CIRCLE_BACK
    assert mock_chat_ai_verify_scheduling_convo.call_count == 0
    assert mock_chat_ai_classify_active_convo.call_count == 1

    messages = [
        "David (7/4): Hey Aakash, would you like to buy an AI solution from me",
        "Aakash (7/6): Give me a call next monday",
    ]
    result = get_prospect_status_from_convo(messages, sdr.id)
    assert result == ProspectStatus.ACTIVE_CONVO_SCHEDULING
    assert mock_chat_ai_verify_scheduling_convo.call_count == 1
    assert mock_chat_ai_classify_active_convo.call_count == 1

    with mock.patch(
        "src.voyager.services.chat_ai_verify_scheduling_convo", return_value=False
    ) as mock_chat_ai_verify_scheduling_convo:
        messages = [
            "David (7/4): Hey Aakash, would you like to buy an AI solution from me",
            "Aakash (7/6): I dislike this conversation and I hate monday.",
        ]
        result = get_prospect_status_from_convo(messages, sdr.id)
        assert result == ProspectStatus.ACTIVE_CONVO_CIRCLE_BACK
        assert mock_chat_ai_verify_scheduling_convo.call_count == 1
        assert mock_chat_ai_classify_active_convo.call_count == 2
