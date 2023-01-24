from app import app
from decorators import use_app_context
from test_utils import (
    test_app
)

from src.research.linkedin.services import (
    sanitize_payload,
    get_iscraper_payload_error
)
import pytest

EXAMPLE_PAYLOAD = {
    "personal": {
        "position_groups": [
            {
                "company": {
                    "name": "Athelas"
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
    