from model_import import ResearchPayload, ResearchPoints

from src.research.extractor_transformer import ExtractorAndTransformer
from src.research.website.serp_helpers import search_google_news
from src.research.website.serp_company_news import create_company_news_summary_point


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

    def __init__(self, prospect_id, configuration):
        self.configuration = configuration
        super().__init__(prospect_id)

    def create_payload(self):
        payload = {}
        for config_key in self.configuration:
            config_val = self.configuration[config_key]
            query = config_val["query"]
            intext = config_val["intext"]
            exclude = config_val["exclude"]
            result = search_google_news(query=query, intext=intext, exclude=exclude)

            result.update({"query": query, "intext": intext, "exclude": exclude})
            payload[config_key] = result

        # Create the payload
        # Return the payload_id

        return payload

    def from_payload_create_points(self, payload_id):
        payload = ResearchPayload.get_by_id(payload_id)

        self.help_create_company_news_summary(payload)

        pass

    def help_create_company_news_summary(self, payload):
        if "recent_company_news" in payload:
            payload_item = payload["recent_company_news"]
            query = payload_item["query"]
            article_title = payload_item["title"]
            article_date = payload_item["date"]
            article_snippet = payload_item["snippet"]
            article_source = payload_item["source"]

            response = create_company_news_summary_point(
                company_name=query,
                article_title=article_title,
                article_date=article_date,
                article_snippet=article_snippet,
                article_source=article_source,
            )

            # Create the point
        return
