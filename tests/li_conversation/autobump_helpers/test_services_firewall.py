from app import db
from decorators import use_app_context
from src.li_conversation.autobump_helpers.services_firewall import (
    rule_cant_be_blank,
    rule_default_framework,
    rule_minimum_character_count,
    rule_no_blacklist_words,
    rule_no_sdr_name_in_message,
    rule_no_stale_message,
    rule_no_profanity,
    run_autobump_firewall,
)
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_bump_framework,
    basic_generated_message_autobump,
)
from datetime import datetime, timedelta


@use_app_context
def test_run_autobump_firewall():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    framework = basic_bump_framework(sdr, archetype, default=True)

    good_message = (
        "Hi! Just wanted to bump this message and see if you are still interested?"
    )

    # No violations
    autobump = basic_generated_message_autobump(
        prospect, sdr, framework, message=good_message
    )
    result, violations = run_autobump_firewall(autobump.id)
    assert result == True
    assert violations == []

    # Violations
    autobump = basic_generated_message_autobump(prospect, sdr, framework, message=" ")
    result, violations = run_autobump_firewall(autobump.id)
    assert result == False
    assert violations == [
        "Message shorter than 15 characters.",
        "Message is blank.",
    ]


@use_app_context
def test_rule_no_blacklist_words():
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr.blacklisted_words = ["bad", "words"]

    message = "This message is clean"
    violations = []
    rule_no_blacklist_words(message, violations, sdr.id)
    assert violations == []

    message = "This message contains bad words"
    violations = []
    rule_no_blacklist_words(message, violations, sdr.id)
    assert violations == ["Message contains blacklisted words: 'bad', 'words'"]


@use_app_context
def test_rule_minimum_character_count():
    message = "THIS MESSAGE IS OVER 15 CHARACTERS"
    violations = []
    rule_minimum_character_count(message, violations)
    assert violations == []

    message = "SHORT"
    violations = []
    rule_minimum_character_count(message, violations)
    assert violations == ["Message shorter than 15 characters."]


@use_app_context
def test_rule_cant_be_blank():
    message = "THIS MESSAGE IS NOT BLANK"
    violations = []
    rule_cant_be_blank(message, violations)
    assert violations == []

    message = " "
    violations = []
    rule_cant_be_blank(message, violations)
    assert violations == ["Message is blank."]


@use_app_context
def test_rule_default_framework():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)

    # Default Framework
    framework = basic_bump_framework(sdr, archetype, default=True)
    autobump = basic_generated_message_autobump(prospect, sdr, framework)
    violations = []
    rule_default_framework(autobump.id, violations)
    assert violations == []

    # Not Default Framework
    framework = basic_bump_framework(sdr, archetype, default=False)
    autobump = basic_generated_message_autobump(prospect, sdr, framework)
    violations = []
    rule_default_framework(autobump.id, violations)
    assert violations == [f"Bump framework (#{framework.id}) is not default"]


@use_app_context
def test_rule_no_stale_message():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    framework = basic_bump_framework(sdr, archetype, default=True)

    # Stale message
    autobump = basic_generated_message_autobump(prospect, sdr, framework)
    autobump_id = autobump.id
    autobump.created_at = datetime.now() - timedelta(days=4)
    db.session.commit()
    violations = []
    rule_no_stale_message(autobump_id, violations)
    assert violations == ["Message is stale (generated more than 3 days ago)"]

    # Not stale message
    autobump = basic_generated_message_autobump(prospect, sdr, framework)
    autobump_id = autobump.id
    autobump.created_at = datetime.now() - timedelta(days=1)
    db.session.commit()
    violations = []
    rule_no_stale_message(autobump_id, violations)
    assert violations == []


@use_app_context
def test_rule_no_sdr_name_in_message():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    framework = basic_bump_framework(sdr, archetype, default=True)

    # Contains SDR name
    autobump = basic_generated_message_autobump(
        prospect, sdr, framework, message="Hi, my name is " + sdr.name + ":"
    )
    autobump_id = autobump.id
    violations = []
    rule_no_sdr_name_in_message(autobump_id, violations)
    assert violations == ["Message contains SDR name"]

    # Does not contain SDR name
    autobump = basic_generated_message_autobump(
        prospect, sdr, framework, message="Hi, my name is not"
    )
    autobump_id = autobump.id
    violations = []
    rule_no_sdr_name_in_message(autobump_id, violations)
    assert violations == []


@use_app_context
def test_rule_no_profanity():
    message = "This message is clean"
    violations = []
    rule_no_profanity(message, violations)
    assert violations == []

    message = "This message is not clean, shit."
    violations = []
    rule_no_profanity(message, violations)
    assert violations == ["Message contains profanity: 'shit'"]
