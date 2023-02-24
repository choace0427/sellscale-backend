from app import app, db
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_research_payload,
    basic_iscraper_payload_cache,
    clear_all_entities
)
from src.research.linkedin.services import (
    sanitize_payload,
    get_iscraper_payload_error,
    get_research_payload_new
)
from model_import import IScraperPayloadCache, ResearchPayload
from freezegun import freeze_time
import pytest
import mock
from datetime import datetime, timedelta

EXAMPLE_PAYLOAD = {
    "personal": {
        "position_groups": [
            {
                "company": {
                    "name": "Athelas",
                    "url": "https://www.linkedin.com/company/athelas/"
                }
            },
            {
                "company": {
                    "name": "Curative (acq. Doximity)"
                }
            },
        ]
    },
    "company": {
        "details": {
            "name": "HEAL Security | Cognitive Cybersecurity Intelligence for the Healthcare Sector"
        }
    }
}

@use_app_context
def test_sanitize_payload():
    response = sanitize_payload(EXAMPLE_PAYLOAD)
    assert response["company"]["details"]["name"] == "HEAL Security"
    assert response["personal"]["position_groups"][0]["company"]["name"] == "Athelas"
    assert response["personal"]["position_groups"][1]["company"]["name"] == "Curative"


@use_app_context
def test_get_iscraper_payload_error():
    payload_with_message = {"message": "API rate limit exceeded"}
    error = get_iscraper_payload_error(payload_with_message)
    assert error == "API rate limit exceeded"

    payload_with_detail = {"detail": "Profile data cannot be retrieved."}
    error = get_iscraper_payload_error(payload_with_detail)
    assert error == "Profile data cannot be retrieved."

    payload_with_none = {}
    error = get_iscraper_payload_error(payload_with_none)
    assert error == "iScraper error not provided"

    with pytest.raises(ValueError):
        valid_payload = {"first_name": "test"}
        error = get_iscraper_payload_error(valid_payload)


@use_app_context
def test_get_research_payload_new_payload_exists():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect.linkedin_url = "https://www.linkedin.com/in/test"

    # Payload exists
    payload = basic_research_payload(prospect)
    returned = get_research_payload_new(prospect_id)
    assert returned == payload.payload

@use_app_context
@mock.patch("src.research.linkedin.services.research_personal_profile_details", return_value=EXAMPLE_PAYLOAD)
@mock.patch("src.research.linkedin.services.research_corporate_profile_details", return_value={"company": "Fake Company"})
def test_get_research_payload_new(mock_iscraper_personal, mock_iscraper_company):
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect.linkedin_url = "https://www.linkedin.com/in/test"

    # iScraper Cache Exists
    cache = basic_iscraper_payload_cache(prospect.id)
    returned = get_research_payload_new(prospect.id)
    assert returned == {"personal": cache.payload, "company": {"company": "Fake Company"}}

    clear_all_entities(ResearchPayload)
    clear_all_entities(IScraperPayloadCache)

    # iScraper Cache Exists but is too old
    cache = basic_iscraper_payload_cache(prospect.id)
    with freeze_time(datetime.now() + timedelta(weeks=3)):
        returned = get_research_payload_new(prospect_id)
        assert returned == {"personal": EXAMPLE_PAYLOAD, "company": {"company": "Fake Company"}}

