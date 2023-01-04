import mock
from decorators import use_app_context
from test_utils import test_app

from src.research.website.serp_company_news import *

MOCK_OPENAI_RESPONSE = {
    "choices": [
        {
            "text": "test-text"
        }
    ]
}


@use_app_context
@mock.patch("openai.Completion.create", return_value=MOCK_OPENAI_RESPONSE)
def test_get_openai_article_summary(openai_mock):
    company = "SellScale"
    article_source = "test-source"
    article_title = "test-title"
    article_snippet = "test-snippet"
    article_date = "test-date"

    result = create_company_news_summary_point(company_name=company, article_source=article_source,
                                               article_title=article_title, article_snippet=article_snippet, article_date=article_date)
    assert openai_mock.call_count == 1
    assert result == "test-text"
