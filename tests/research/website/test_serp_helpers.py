from src.research.website.serp_helpers import *
from decorators import use_app_context
from test_utils import test_app

import mock

MOCK_SERP_RESPONSE = {
    "news_results": [
        {
            "title": "test-title",
            "link": "test-link",
            "date": "test-date",
            "source": "test-source",
            "snippet": "test-snippet",
            "category": "test-category",
            "thumbnail": "test-thumbnail",
        }
    ]
}


class MockGoogleSearch:
    def get_dict():
        return MOCK_SERP_RESPONSE


@use_app_context
@mock.patch(
    "src.research.website.serp_helpers.GoogleSearch", return_value=MockGoogleSearch
)
def test_search_google_news(serp_mock):
    query = "SellScale"
    search_google_news(query=query)
    serp_mock.assert_called_once_with(
        {
            "api_key": None,
            "engine": "google",
            "q": '"SellScale"',
            "tbm": "nws",
            "gl": "us",
            "hl": "en",
            "tbm": "nws",
        }
    )

    # Single intext
    query = "SellScale"
    intext = ["skyrocket"]
    search_google_news(query=query, intext=intext)
    serp_mock.assert_called_with(
        {
            "api_key": None,
            "engine": "google",
            "q": '"SellScale" (intext:"skyrocket")',
            "tbm": "nws",
            "gl": "us",
            "hl": "en",
            "tbm": "nws",
        }
    )

    # Multiple intext
    query = "SellScale"
    intext = ["skyrocket", "growth"]
    search_google_news(query=query, intext=intext)
    serp_mock.assert_called_with(
        {
            "api_key": None,
            "engine": "google",
            "q": '"SellScale" (intext:"skyrocket" OR intext:"growth")',
            "tbm": "nws",
            "gl": "us",
            "hl": "en",
            "tbm": "nws",
        }
    )

    # Exclude
    query = "SellScale"
    intext = ["skyrocket", "growth"]
    exclude = ["lost", "fear"]
    search_google_news(query=query, intext=intext, exclude=exclude)
    serp_mock.assert_called_with(
        {
            "api_key": None,
            "engine": "google",
            "q": '"SellScale" (intext:"skyrocket" OR intext:"growth") -lost -fear',
            "tbm": "nws",
            "gl": "us",
            "hl": "en",
            "tbm": "nws",
        }
    )

    result = search_google_news(query=query, intext=intext, exclude=exclude)
    assert result["source"] == "test-source"
    assert result["title"] == "test-title"
    assert result["snippet"] == "test-snippet"
    assert result["date"] == "test-date"
