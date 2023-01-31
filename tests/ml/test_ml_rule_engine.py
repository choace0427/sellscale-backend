from app import db, app
from test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_generated_message,
    basic_gnlp_model,
    basic_prospect,
)
from decorators import use_app_context
from src.ml.rule_engine import (
    run_message_rule_engine,
    wipe_problems,
    format_entities,
    rule_no_profanity,
    rule_no_cookies,
    rule_no_url,
    rule_linkedin_length,
    rule_address_doctor,
    rule_no_symbols,
    rule_no_companies,
    rule_catch_strange_titles
)
from model_import import GeneratedMessage, GeneratedMessageType


@use_app_context
def test_run_message_rule_engine():
    #TODO Add specific tests for each rule
    pass


@use_app_context
def test_wipe_problems():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message.problems = ["test"]
    generated_message.unknown_named_entities = ["test"]
    db.session.add(generated_message)
    db.session.commit()

    wipe_problems(generated_message.id)

    assert GeneratedMessage.query.get(generated_message.id).problems == []
    assert GeneratedMessage.query.get(generated_message.id).unknown_named_entities == []


@use_app_context
def test_format_entities():
    problems = []
    format_entities(["test"], problems)
    assert problems == ["Potential wrong name: 'test'"]

    problems = []
    format_entities(["test", "test2"], problems)
    assert problems == ["Potential wrong name: 'test'", "Potential wrong name: 'test2'"]


@use_app_context
def test_rule_no_profanity():
    problems = []
    rule_no_profanity("pass", problems)
    assert problems == []

    rule_no_profanity("Oh shit this one will definitely get flagged", problems)
    assert problems == ["Contains profanity: 'shit'"]

    problems = []
    rule_no_profanity("fuck shit bitch", problems)
    assert problems == ["Contains profanity: 'fuck', 'shit', 'bitch'"]

    problems = []
    rule_no_profanity("shit!", problems)
    assert problems == ["Contains profanity: 'shit'"]


@use_app_context
def test_rule_no_cookies():
    problems = []
    rule_no_cookies("pass", problems)
    assert problems == []

    rule_no_cookies("Wow you use javascript in your browser? That's advanced!", problems)
    assert problems == ["Contains web related words: 'javascript', 'browser'. Please check for relevance."]


@use_app_context
def test_rule_no_url():
    problems = []
    rule_no_url("pass", problems)
    assert problems == []

    rule_no_url("https://www.google.com", problems)
    assert problems == ["Contains a URL."]


@use_app_context
def test_rule_linkedin_length():
    problems = []
    rule_linkedin_length(GeneratedMessageType.EMAIL, "pass", problems)
    assert problems == []

    rule_linkedin_length(GeneratedMessageType.LINKEDIN, "pass", problems)
    assert problems == []

    big_message = "long"
    for i in range(300):
        big_message += "message"
    
    assert len(big_message) > 300
    rule_linkedin_length(GeneratedMessageType.LINKEDIN, big_message, problems)
    assert problems == ["LinkedIn message is > 300 characters."]


@use_app_context
def test_rule_address_doctor():
    problems = []
    rule_address_doctor("name: David<>title: ", "pass", problems)
    assert problems == []

    rule_address_doctor("name: Dr. David<>title:", "pass", problems)
    assert problems == []

    rule_address_doctor("name: David, MD<>title:", "dr. David", problems)
    assert problems == []

    problems = []
    rule_address_doctor("name: David, MD<>title:", "David", problems)
    assert problems == ["Name contains 'MD' but no 'Dr.' in message"]

    problems = []
    rule_address_doctor("name: David Wei<>title: physician at some hospital<>", "David, MD", problems)
    assert problems == ["Title contains a doctor position 'physician' but no 'Dr.' in message"]

    problems = []
    rule_address_doctor("name: David Wei, <>title: neurosurgeon at some hospital", "David, MD", problems)
    assert problems == ["Title contains a doctor position 'neurosurgeon' but no 'Dr.' in message"]

    problems = []
    rule_address_doctor("name: David Wei, <>title: M.D. at Kaiser", "David, MD", problems)
    assert problems == ["Title contains 'MD' but no 'Dr.' in message"]

    problems = []
    rule_address_doctor("name: David Wei, Neurosurgeon<>title: nothing", "David, MD", problems)
    assert problems == ["Name contains a doctor position 'neurosurgeon' but no 'Dr.' in message"]


@use_app_context
def test_rule_no_symbols():
    problems = []
    rule_no_symbols("pass", problems)
    assert problems == []

    rule_no_symbols("This is a message with a passing symbol: !", problems)
    assert problems == []

    rule_no_symbols("This is a message with a failing symbol: $", problems)
    assert problems == ["Completion contains uncommon symbols: $"]

    problems = []
    rule_no_symbols("This is a message with a failing symbol: $ ®", problems)
    assert problems == ["Completion contains uncommon symbols: $, ®"]


@use_app_context
def test_rule_no_companies():
    problems = []
    rule_no_companies("pass", problems)
    assert problems == []

    rule_no_companies("This is a message with a an abbreviation: Something inc", problems)
    assert problems == ["Please check for relevance. Contains company abbreviations: inc"]

    problems = []
    rule_no_companies("This is a message with a an abbreviation: Something inc. and another one: Something else ltd.", problems)
    assert problems == ["Please check for relevance. Contains company abbreviations: inc, ltd"]


@use_app_context
def test_rule_catch_strange_titles():
    problems = []
    rule_catch_strange_titles("pass", "pass", problems)
    assert problems == []

    rule_catch_strange_titles("pass", "David Wei<>title: Software Engineer at SellScale<>something:dddd", problems)
    assert problems == []

    rule_catch_strange_titles("I like what you do as a Software Engineer", "David Wei<>title: Software Engineer | Growth Man<>something:dddd", problems)
    assert problems == ["WARNING: Title is mentioned but original title contains symbols, check for quality."]

    problems = []
    rule_catch_strange_titles("I like what you do as a Software Engineer", "David Wei<>title: Software Engineer at SellScale but way too many characters here<>something:", problems)
    assert problems == ["WARNING: Title is mentioned but original title is too long, check for quality."]
