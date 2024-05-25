import os
from typing import Optional
from serpapi import GoogleSearch


def search_google_news(query: str, intext: any = [], exclude: any = []):
    """Use SERP API to search Google News for a given Query. Returns the top 3 results.

    Helpful websearch commands:
    - https://support.google.com/websearch/answer/2466433?hl=en
    - https://www.searchenginejournal.com/google-search-operators-commands/215331/

    TODO: Create default exclude list
    TODO: Create heuristic for selecting top result

    Args:
        query (str): The query to search for.
        intext (list[str]): A list of strings to search for in the results.
        exclude (list[str]): A list of strings to exclude from the results.

    Returns:
        dict: Dictionary of fields from SERP API's top result.
    """
    serp_api_key = os.getenv("SERP_API_KEY")

    # Sample full_q: '"SellScale" (intext:"skyrocket" OR intext:"growth" OR intext:"fundraise" OR intext:"market") -lost -fear'
    full_q = f'"{query}"'
    if intext:
        full_q += f' (intext:"{intext[0]}"'
        for i in range(1, len(intext)):
            full_q += f' OR intext:"{intext[i]}"'
        full_q += ")"
    if exclude:
        for e in exclude:
            full_q += f" -{e}"

    params = {
        "api_key": serp_api_key,
        "engine": "google",
        "q": full_q,
        "tbm": "nws",
        "gl": "us",  # US only
        "hl": "en",
        "tbm": "nws",
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    news_results: list = results.get("news_results", [])
    if len(news_results) == 0:
        return {}
    top_result = results["news_results"][0]

    return {
        "title": top_result.get("title"),
        "link": top_result.get("link"),
        "date": top_result.get("date"),
        "source": top_result.get("source"),
        "snippet": top_result.get("snippet"),
        "category": top_result.get("category"),
        "thumbnail": top_result.get("thumbnail"),
    }


def search_google_news_raw(query, type: Optional[str] = None, engine: Optional[str] = "google", start: Optional[int] = 0):
    # https://support.google.com/websearch/answer/2466433?hl=en
    serp_api_key = os.getenv("SERP_API_KEY")
    NUM_GOOGLE_RESULTS_TO_SCRAPE = 10
    
    params = {
        "api_key": serp_api_key,
        "engine": engine,
        "q": query,
        "tbm": type,
        "gl": "us",  # US only
        "hl": "en",
        "num": NUM_GOOGLE_RESULTS_TO_SCRAPE,
        "start": start
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    return results
