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
    rule_catch_no_i_have,
    rule_no_profanity,
    rule_no_cookies,
    rule_catch_has_6_or_more_consecutive_upper_case,
    rule_no_url,
    rule_linkedin_length,
    rule_address_doctor,
    rule_no_symbols,
    rule_no_companies,
    rule_catch_strange_titles,
    rule_no_hard_years,
    rule_catch_im_a,
)
from model_import import GeneratedMessage, GeneratedMessageType


@use_app_context
def test_run_message_rule_engine():
    # TODO Add specific tests for each rule
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
    highlighted_words = []
    format_entities(["test"], problems, highlighted_words)

    assert problems == ["Potential wrong name: 'test'"]
    assert highlighted_words == ["test"]

    problems = []
    highlighted_words = []
    format_entities(["test", "test2"], problems, highlighted_words)
    assert problems == ["Potential wrong name: 'test'", "Potential wrong name: 'test2'"]
    assert highlighted_words == ["test", "test2"]


@use_app_context
def test_rule_no_profanity():
    problems = []
    highlighted_words = []
    rule_no_profanity("pass", problems, highlighted_words)
    assert problems == []

    rule_no_profanity(
        "Oh shit this one will definitely get flagged", problems, highlighted_words
    )
    assert problems == ["Contains profanity: 'shit'"]
    assert highlighted_words == ["shit"]

    problems = []
    highlighted_words = []
    rule_no_profanity("fuck shit bitch", problems, highlighted_words)
    assert problems == ["Contains profanity: 'fuck', 'shit', 'bitch'"]
    assert highlighted_words == ["fuck", "shit", "bitch"]

    problems = []
    highlighted_words = []
    rule_no_profanity("shit!", problems, highlighted_words)
    assert problems == ["Contains profanity: 'shit'"]
    assert highlighted_words == ["shit"]


@use_app_context
def test_rule_no_cookies():
    problems = []
    highlighted_words = []
    rule_no_cookies("pass", problems, highlighted_words)
    assert problems == []

    rule_no_cookies(
        "Wow you use javascript in your browser? That's advanced!",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Contains web related words: 'javascript', 'browser'. Please check for relevance."
    ]
    assert highlighted_words == ["javascript", "browser"]


@use_app_context
def test_rule_no_url():
    problems = []
    highlighted_words = []
    rule_no_url("pass", problems, highlighted_words)
    assert problems == []

    rule_no_url("https://www.google.com", problems, highlighted_words)
    assert problems == ["Contains a URL."]
    assert highlighted_words == ["www."]


@use_app_context
def test_rule_linkedin_length():
    problems = []
    highlighted_words = []
    rule_linkedin_length(
        GeneratedMessageType.EMAIL, "pass", problems, highlighted_words
    )
    assert problems == []

    rule_linkedin_length(
        GeneratedMessageType.LINKEDIN, "pass", problems, highlighted_words
    )
    assert problems == []

    big_message = "long"
    for i in range(300):
        big_message += "message"

    assert len(big_message) > 300
    rule_linkedin_length(
        GeneratedMessageType.LINKEDIN, big_message, problems, highlighted_words
    )
    assert problems == ["LinkedIn message is > 300 characters."]


@use_app_context
def test_rule_address_doctor():
    problems = []
    highlighted_words = []
    rule_address_doctor("name: David<>title: ", "pass", problems, highlighted_words)
    assert problems == []

    rule_address_doctor("name: Dr. David<>title:", "pass", problems, highlighted_words)
    assert problems == []

    rule_address_doctor(
        "name: David, MD<>title:", "dr. David", problems, highlighted_words
    )
    assert problems == []

    problems = []
    highlighted_words = []
    rule_address_doctor("name: David, MD<>title:", "David", problems, highlighted_words)
    assert problems == ["Name contains 'MD' but no 'Dr.' in message"]
    assert highlighted_words == ["name:", "david,", "md"]

    problems = []
    rule_address_doctor(
        "name: David Wei<>title: physician at some hospital<>",
        "David, MD",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Title contains a doctor position 'physician' but no 'Dr.' in message"
    ]
    assert highlighted_words == ["name:", "david,", "md", "name:", "david", "wei"]

    problems = []
    highlighted_words = []
    rule_address_doctor(
        "name: David Wei, <>title: neurosurgeon at some hospital",
        "David, MD",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Title contains a doctor position 'neurosurgeon' but no 'Dr.' in message"
    ]
    assert highlighted_words == ["name:", "david", "wei,", ""]

    problems = []
    highlighted_words = []
    rule_address_doctor(
        "name: David Wei, <>title: M.D. at Kaiser",
        "David, MD",
        problems,
        highlighted_words,
    )
    assert problems == ["Title contains 'MD' but no 'Dr.' in message"]
    assert highlighted_words == ["name:", "david", "wei,", ""]

    problems = []
    highlighted_words = []
    rule_address_doctor(
        "name: David Wei, Neurosurgeon<>title: nothing",
        "David, MD",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Name contains a doctor position 'neurosurgeon' but no 'Dr.' in message"
    ]
    assert highlighted_words == ["name:", "david", "wei,", "neurosurgeon"]

    problems = []
    highlighted_words = []
    rule_address_doctor(
        "name: Darshan Kamdar, <>title: something",
        "Hey Darshan, something",
        problems,
        highlighted_words,
    )
    assert problems == []
    assert highlighted_words == []


@use_app_context
def test_no_i_have():
    problems = []
    highlighted_words = []
    rule_catch_no_i_have("pass", "", problems, highlighted_words)
    assert problems == []
    assert highlighted_words == []

    rule_catch_no_i_have(
        "i have a bad feeling about this", "", problems, highlighted_words
    )
    assert problems == ["Uses first person 'I have'."]
    assert highlighted_words == ["i have"]


@use_app_context
def test_rule_catch_has_6_or_more_consecutive_upper_case():
    problems = []
    highlighted_words = []
    rule_catch_has_6_or_more_consecutive_upper_case(
        "pass", "", problems, highlighted_words
    )
    assert problems == []
    assert highlighted_words == []

    rule_catch_has_6_or_more_consecutive_upper_case(
        "I work at NASA AMES CENTER but this is kinda swaggy",
        "",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Contains a long, uppercase word. Verify that names are capitalized correctly."
    ]
    assert highlighted_words == ["NASA AMES CENTER"]

    problems = []
    highlighted_words = []
    rule_catch_has_6_or_more_consecutive_upper_case(
        "Kudos on all your experiences at ARDEA BIOSCIENCES.",
        "",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Contains a long, uppercase word. Verify that names are capitalized correctly."
    ]
    assert highlighted_words == ["ARDEA BIOSCIENCES"]

    problems = []
    highlighted_words = []
    rule_catch_has_6_or_more_consecutive_upper_case(
        "Kudos on all your experiences at Ardea.",
        "",
        problems,
        highlighted_words,
    )
    assert problems == []
    assert highlighted_words == []

    rule_catch_has_6_or_more_consecutive_upper_case(
        "Impressive background of experience in Automotive, especially at KIA CANADA! It looks like you all are offering innovative and dynamic products and services through a network of 197 dealers, which is incredible. Keep up the good work!",
        "",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Contains a long, uppercase word. Verify that names are capitalized correctly."
    ]
    assert highlighted_words == ["KIA CANADA"]


@use_app_context
def test_should_not_catch_have():
    problems = []
    highlighted_words = []
    rule_catch_no_i_have("pass", "", problems, highlighted_words)
    assert problems == []
    assert highlighted_words == []

    rule_catch_no_i_have(
        "mahendra modi have a bad feeling about this", "", problems, highlighted_words
    )
    assert problems == []
    assert highlighted_words == []


@use_app_context
def test_rule_no_symbols():
    problems = []
    highlighted_words = []
    rule_no_symbols("pass", problems, highlighted_words)
    assert problems == []

    rule_no_symbols(
        "This is a message with a passing symbol: !", problems, highlighted_words
    )
    assert problems == []

    rule_no_symbols(
        "This is a message with a failing symbol: $", problems, highlighted_words
    )
    assert problems == ["Completion contains uncommon symbols: $"]

    problems = []
    rule_no_symbols(
        "This is a message with a failing symbol: $ ®", problems, highlighted_words
    )
    assert problems == ["Completion contains uncommon symbols: $, ®"]


@use_app_context
def test_rule_no_companies():
    problems = []
    highlighted_words = []
    rule_no_companies("pass", problems, highlighted_words)
    assert problems == []

    rule_no_companies(
        "This is a message with a an abbreviation: Something inc",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Please check for relevance. Contains company abbreviations: inc"
    ]

    problems = []
    rule_no_companies(
        "This is a message with a an abbreviation: Something inc. and another one: Something else ltd.",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Please check for relevance. Contains company abbreviations: inc, ltd"
    ]


@use_app_context
def test_rule_catch_strange_titles():
    problems = []
    highlighted_words = []
    rule_catch_strange_titles("pass", "pass", problems, highlighted_words)
    assert problems == []
    assert highlighted_words == []

    rule_catch_strange_titles(
        "pass",
        "David Wei<>title: Software Engineer at SellScale<>something:dddd",
        problems,
        highlighted_words,
    )
    assert problems == []
    assert highlighted_words == []

    rule_catch_strange_titles(
        "Hi David, I really like what you do as the VP of Engineering",
        "David Wei<>title: VP of Engineering and Growth",
        problems,
        highlighted_words,
    )
    assert problems == []
    assert highlighted_words == []

    rule_catch_strange_titles(
        "I like what you do as a Software Engineer",
        "David Wei<>title: Software @ Engineer",
        problems,
        highlighted_words,
    )
    assert problems == []
    assert highlighted_words == []

    rule_catch_strange_titles(
        "Hi David, I really like what you do as the VP of Engineering and Growth",
        "David Wei<>title: VP of Engineering and Growth",
        problems,
        highlighted_words,
    )
    assert problems == [
        "WARNING: Prospect's job title may be too long. Please simplify it to sound more natural. (e.g. VP Growth and Marketing → VP Marketing)"
    ]
    assert highlighted_words == ["VP of Engineering and"]

    problems = []
    highlighted_words = []
    rule_catch_strange_titles(
        "Hi David, I really like what you do as the Software @@ Engineering",
        "David Wei<>title: Software @@ Engineering",
        problems,
        highlighted_words,
    )
    assert problems == [
        "WARNING: Prospect's job title contains strange symbols. Please remove any strange symbols."
    ]
    assert highlighted_words == ["Software @@ Engineering"]


@use_app_context
def test_rule_no_hard_years():
    problems = []
    highlighted_words = []
    rule_no_hard_years("pass", "pass", problems, highlighted_words)
    assert problems == []
    assert highlighted_words == []

    rule_no_hard_years(
        "I see you've been at SellScale for 5 years",
        "half a decade",
        problems,
        highlighted_words,
    )
    assert problems == [
        "Please reference years in colloquial terms. (e.g. 5 years → half a decade)"
    ]
    assert highlighted_words == ["5 years"]


@use_app_context
def test_rule_no_im_a():
    problems = []
    highlighted_words = []
    rule_catch_im_a(
        "I'm a physician recruiter and this is a lie!",
        "pass",
        problems,
        highlighted_words,
    )
    assert problems == [
        'Found "I\'m a" in the completion. Ensure that the completion is not making false claims.'
    ]
    assert highlighted_words == ["I'm a"]

    problems = []
    highlighted_words = []
    rule_catch_im_a(
        "I'm a physician recruiter and that's for real!",
        "I'm a physician recruiter",
        problems,
        highlighted_words,
    )
    assert problems == []
    assert highlighted_words == []

    problems = []
    highlighted_words = []
    rule_catch_im_a(
        "I'm a huge fan of your work!",
        "pass",
        problems,
        highlighted_words,
    )
    assert problems == []
    assert highlighted_words == []
