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
    rule_no_url,
)
from model_import import GeneratedMessage

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
def test_rule_no_url():
    problems = []
    rule_no_url("pass", problems)
    assert problems == []

    rule_no_url("https://www.google.com", problems)
    assert problems == ["Contains a URL."]
