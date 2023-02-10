from model_import import (
    ResearchPayload,
    ResearchPointType,
    ResearchType,
    ResearchPoints,
    Prospect,
)
from src.research.services import create_research_payload, create_research_point
from src.research.extractor_transformer import ExtractorAndTransformer
from src.research.website.serp_helpers import search_google_news
from src.research.website.serp_company_news import (
    create_company_news_summary_point,
    analyze_serp_article_sentiment,
)


class SerpNewsExtractorTransformer(ExtractorAndTransformer):
    """Takes a prospect_id and configuration to create a payload and points.

    This class will take the user provided configuration and use it to create a research payload which includes SERP returned fields.
    These fields will then be summarized by OpenAI. The top result from each search will be used, pending a heuristic.

    Example configuration:

    ```
    configuration = {
        "recent_company_news": {
            "query": "Company_name",
            "intext": ["growth", "marketing"],
            "exclude": ["lost", "fear"]
        },
        "recent_weather_news": {
            "query": "Weather in city_name",
            "intext": ["snow", "rain", "storm", "sleet", "hail"],
        }
    }
    ```

    TODO: Add heuristics for article selection
    """

    def __init__(self, prospect_id):
        super().__init__(prospect_id)

        self.prospect: Prospect = Prospect.get_by_id(prospect_id)
        self.configuration = {
            "recent_company_news": {
                "query": self.prospect.company,
                "intext": ["growth", "marketing"],  # TODO replace with client tags
                "exclude": [
                    "lost",
                    "fear",
                    "short interest",
                    "downgrade",
                ],  # TODO replace with client exclusions
            },
        }
        self.payload = ResearchPayload.get_by_prospect_id(
            prospect_id, ResearchType.SERP_PAYLOAD
        )
        if self.payload:
            self.research_points = ResearchPoints.get_by_payload_id(self.payload.id)

    def from_payload_create_points(self, payload_id):
        rp: ResearchPayload = ResearchPayload.get_by_id(payload_id)
        if not rp:
            return None

        payload: dict = rp.payload

        self.help_create_company_news_summary(payload_id, payload)

    def create_payload(self):
        payload = {}
        for config_key in self.configuration:
            config_val = self.configuration[config_key]
            query = config_val["query"]
            intext = config_val["intext"]
            exclude = config_val["exclude"]
            result = search_google_news(query=query, intext=intext, exclude=exclude)

            if not result.get("title"):
                return None

            result.update({"query": query, "intext": intext, "exclude": exclude})
            payload[config_key] = result

        payload_id = create_research_payload(
            prospect_id=self.prospect_id,
            research_type=ResearchType.SERP_PAYLOAD,
            payload=payload,
        )
        return payload_id

    def help_create_company_news_summary(self, payload_id: int, payload: dict):
        if "recent_company_news" in payload:
            payload_item = payload["recent_company_news"]
            query = payload_item["query"]
            article_title = payload_item["title"]
            article_date = payload_item["date"]
            article_snippet = payload_item["snippet"]
            article_source = payload_item["source"]

            research_point_text = create_company_news_summary_point(
                company_name=query,
                article_title=article_title,
                article_date=article_date,
                article_snippet=article_snippet,
                article_source=article_source,
            )
            article_sentiment = analyze_serp_article_sentiment(
                article_title=article_title,
                article_snippet=article_snippet,
            )

            RESEARCH_POINT_TYPE = ResearchPointType.SERP_NEWS_SUMMARY_NEGATIVE
            if article_sentiment == "positive":
                RESEARCH_POINT_TYPE = ResearchPointType.SERP_NEWS_SUMMARY
            create_research_point(
                payload_id=payload_id,
                research_point_type=RESEARCH_POINT_TYPE,
                text=research_point_text,
                research_point_metadata={"article_sentiment": article_sentiment},
            )

        return True
