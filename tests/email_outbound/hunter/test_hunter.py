from app import db
from src.email_outbound.email_store.hunter import get_email_from_hunter, verify_email_from_hunter
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_sei_raw,
)
import mock


class MockHunterResponse:
        def __init__(self):
            self.status_code = 200
            self.data =  {
                "data": {
                    "email": "test@email.com",
                    "score": 100,
                }
            }

        def json(self):
            return self.data


@use_app_context
@mock.patch("src.email_outbound.email_store.hunter.requests.get", return_value=MockHunterResponse())
def test_get_email_from_hunter(mock_get):
    success, data = get_email_from_hunter(
        first_name="test",
        last_name="test",
        company_website="test.com",
        company_name="test",
    )
    assert success
    assert data["email"] == "test@email.com"
    assert data["score"] == 100
    assert mock_get.call_count == 1


@use_app_context
@mock.patch("src.email_outbound.email_store.hunter.requests.get", return_value=MockHunterResponse())
def test_verify_email_from_hunter(mock_get):
    success, data = verify_email_from_hunter(
        email_address="test@email.com",
    )
    assert success
    assert mock_get.call_count == 1
