from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import test_app
from app import app
import mock

from src.research.linkedin.extractors.current_company import get_current_company_description


GOOD_PAYLOAD = {
    "company": {
        "details": {
            "name": "SellScale",
            "description": "SellScale go brr"
        }
    }
}

BAD_PAYLOAD = {

}


@use_app_context
@mock.patch("src.research.linkedin.extractors.current_company.wrapped_create_completion", return_value="test")
def test_get_current_company_description(openai_mock):
    response = get_current_company_description(GOOD_PAYLOAD)
    assert openai_mock.call_count == 1
    assert response.get("raw_data") == {"company_name": "SellScale", "company_description": "SellScale go brr"}
    assert response.get("prompt") == "company: SellScale\n\nbio: SellScale go brr\n\ninstruction: Summarize what the company does in a short one-liner under 20 words in length.\n\ncompletion:"
    assert response.get("response") == "test"

    response = get_current_company_description(BAD_PAYLOAD)
    assert openai_mock.call_count == 1
    assert response.get("raw_data") == {"company_name": None, "company_description": None}
    assert response.get("prompt") == ""
    assert response.get("response") == ""
