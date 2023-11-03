from src.research.website.serp_news_extractor_transformer import (
    SerpNewsExtractorTransformer,
)
import mock
from tests.test_utils.test_utils import test_app, basic_client, basic_archetype, basic_prospect
from tests.test_utils.decorators import use_app_context
from model_import import ResearchPoints, ResearchPayload


@use_app_context
@mock.patch(
    "src.research.website.serp_news_extractor_transformer.search_google_news",
    return_value={
        "title": "this is a test title",
        "date": "2021-01-01",
        "snippet": "this is",
        "source": "google",
    },
)
@mock.patch(
    "src.research.website.serp_news_extractor_transformer.create_company_news_summary_point",
    return_value="this is a sample research text",
)
@mock.patch(
    "src.research.website.serp_news_extractor_transformer.analyze_serp_article_sentiment", return_value="positive"
)
def test_serp_news_extractor_transformer_class(sentiment_patch, point_patch, serp_patch):
    """Test the SerpNewsExtractorTransformer class."""
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)

    serp_et = SerpNewsExtractorTransformer(prospect.id)
    assert serp_et.prospect.id == prospect.id
    assert serp_et.configuration == {
        "recent_company_news": {
            "query": prospect.company,
            "intext": ["growth", "marketing"],
            "exclude": [
                "lost",
                "fear",
                "short interest",
                "downgrade",
            ],
        },
    }
    assert serp_et.payload is None

    serp_et.run()
    assert point_patch.call_count == 1
    assert sentiment_patch.call_count == 1

    serp_et = SerpNewsExtractorTransformer(prospect.id)
    assert serp_et.payload is not None
    assert serp_patch.call_count == 1

    assert ResearchPoints.query.count() == 1
    assert ResearchPayload.query.count() == 1
