from app import app
from decorators import use_app_context
from test_utils import (
    test_app
)

from src.research.linkedin.services import (
    sanitize_payload,
)

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
    