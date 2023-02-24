from app import db, app
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_prospect,
    basic_archetype,
    basic_linkedin_conversation_entry,
)
from model_import import ProspectOverallStatus, LinkedinConversationEntry
from src.li_conversation.conversation_analyzer.analyzer import (
    run_all_conversation_analyzers,
    run_li_scheduling_conversation_detector,
    detect_scheduling_conversation,
)
import mock


@use_app_context
@mock.patch("src.li_conversation.conversation_analyzer.analyzer.run_li_scheduling_conversation_detector")
def test_run_all_conversation_analyzers(mock_scheduling_detector):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    entry = basic_linkedin_conversation_entry()
    entry_id = entry.id
    prospect.overall_status = ProspectOverallStatus.ACTIVE_CONVO
    prospect.li_conversation_thread_id = entry.conversation_url

    assert entry.entry_processed == False
    result = run_all_conversation_analyzers()
    entry: LinkedinConversationEntry = LinkedinConversationEntry.query.get(entry_id)
    assert result == (True, 1)
    assert entry.entry_processed == True
    assert mock_scheduling_detector.call_count == 1


@use_app_context
@mock.patch("src.li_conversation.conversation_analyzer.analyzer.wrapped_create_completion", return_value="yes")
@mock.patch("src.li_conversation.conversation_analyzer.analyzer.send_slack_message")
def test_run_li_scheduling_conversation_detector(mock_slack, mock_openai):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    entry = basic_linkedin_conversation_entry()
    prospect.overall_status = ProspectOverallStatus.ACTIVE_CONVO
    prospect.li_conversation_thread_id = entry.conversation_url

    run_li_scheduling_conversation_detector([entry.conversation_url])
    assert mock_openai.call_count == 1
    assert mock_slack.call_count == 1


@use_app_context
@mock.patch("src.li_conversation.conversation_analyzer.analyzer.wrapped_create_completion", return_value="yes")
def test_detect_scheduling_conversation(mock_openai):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    entry = basic_linkedin_conversation_entry()
    prospect.overall_status = ProspectOverallStatus.ACTIVE_CONVO
    prospect.li_conversation_thread_id = entry.conversation_url

    result = detect_scheduling_conversation(prospect.id)
    scheduling = result.get("scheduling")
    conversation = result.get("conversation")
    assert scheduling == True
    assert conversation == [f"test_author: '{entry.message}'"]
    assert mock_openai.call_count == 1
