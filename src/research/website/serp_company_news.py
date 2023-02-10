import os
import openai
from src.ml.openai_wrappers import (
    wrapped_create_completion,
    CURRENT_OPENAI_DAVINCI_MODEL,
)


def create_company_news_summary_point(
    company_name: str,
    article_title: str,
    article_date: str,
    article_snippet: str,
    article_source: str,
):
    """Use OpenAI to generate a summary of an article through fewshot learning.

    TODO: Make fewshot learning pull dynamically
    TODO: Add "tags" to the fewshot learning so it is not hardcoded

    Args:
        company_name (str): The company name to search for.
        article_source (str): The source of the article.
        article_date (str): The date of the article.
        article_title (str): The title of the article.
        article_snippet (str): A snippet from the article.

    Returns:
        str: Completion from OpenAI
    """
    openai.api_key = os.getenv("OPENAI_KEY")

    fewshots = "tags: growth, marketing\ncompany: PROS\nsource: PROS\ndate:  1 hour ago\ntitle: Manufacturing Sales CPQ & Pricing Optimization Software\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: The article on PROS about Manafacturing Sales CPQ & Pricing Optimization Software highlighted how AI will power pricing & growth going forward.\n\n-- \n\ntags: growth, marketing\ncompany: Amazon\nsource:  The Motley Fool\ndate:  9 hours ago\ntitle:  Amazon's Advertising Business Still Has Lots of Room for ...\nsnippet:  Amazon's Advertising Business Still Has Lots of Room for Growth. By Adam \nLevy – Dec 26, 2022 at 9:40AM. Key Points. Retail media ad spend is still \ngrowing...\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: The recent Motley Fool feature on Amazon really shows the drastic increase in ad spend across industries. Seems like Amazon has a lot of room to grow in the advertising space.\n\n--\n\ntags: growth, marketing\ncompany: Bacardi\nsource:  BeverageDaily\ndate:  1 day ago\ntitle:  Bacardi reveals top 5 spirit trends for 2023\nsnippet:  Global spirits company Bacardi looks at the key trends it expects to see \n... The growth of e-commerce in the alcohol industry is expected to...\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: I read the article from BeverageDaily about Bacardi's top 5 spirit trends for 2023. Bacardi is leveraging the latest e-commerce technology to level up how they approach growth!\n\n--\n\ntags: growth, marketing\ncompany: CrossFit\nsource:  Fitt Jobs\ndate:  2 days ago\ntitle:  CrossFit Marketing Manager - SPORT in Remote - Fitt\nsnippet:  Help create and execute integrated marketing campaigns to support CrossFit \nSport growth and maximize customer acquisition and retention.\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: I saw the Fitt Jobs post for a CrossFit Marketing Manager that was posted! CrossFit places a big emphasis on growth, customer acquisition and retention.\n\n-- \n\ntags: growth, marketing\ncompany: DigitalOcean\nsource:  Yahoo Finance\ndate:  2 weeks ago\ntitle:  Needham Stays Bullish On DigitalOcean; Says Growth Concerns Already Baked Into Valuation\nsnippet:  Needham Stays Bullish On DigitalOcean; Says Growth Concerns Already Baked \nInto Valuation. Anusuya Lahiri. December 15, 2022 ·2 min read.\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: I read the recent Yahoo Finance article about DigitalOcean's growth potential. Seems that Needham is continuing to remain bullish on the company even with the recent market conditions.\n\n-- \n\ntags: growth, marketing\ncompany: Olist\nsource:  TechCabal\ndate:  Apr 15, 2021\ntitle:  Building in silence: CEO Gbenro Dara speaks on Olist's growth\nsnippet:  In a conversation with TechCabal, Dara Gbenro, CEO of OList talks about ... \nGbenro attributes OList's rapid growth to leveraging Opera's...\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: I just read the TechCabal article about OList's growth. Leveraging Opera's resources is a proven growth strategy and a testament to the power of marketing and partnerships.\n\n--\n\ntags: growth, marketing\ncompany: Alloy Automation\nsource:  TechCrunch\ndate:  Feb 22, 2022\ntitle:  Alloy Automation raises $20M to scale its e-commerce automation tech\nsnippet:  Alloy Automation, a Y Combinator graduate focused on connecting ... of its \nsize when it went out to fundraise, the co-founders said.\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: I just came across the TechCrunch article from February about Alloy's recent $20M raise. Looks like you all are scaling quite quickly and seems like you all have seen a lot of growth since the company's time YCombinator.\n\n-- \n\ntags: growth, marketing\ncompany: TripActions\nsource:  PhocusWire\ndate:  3 weeks ago\ntitle:  TripActions picks up $400M in credit facilities to accelerate ...\nsnippet:  TripActions is bolstering its financial position with $400 million ... \nTripActions says it will use the funding to accelerate growth of its.\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage: I saw the PhocusWire article from a few weeks ago about TripActions's recent $400M in credit facilities. The company is leveraging a strong financial position to fuel growth in this market.\n\n--\n\n"
    prompt = f"tags: growth, marketing\ncompany: {company_name}\nsource: {article_source}\ndate: {article_date}\ntitle: {article_title}\nsnippet: {article_snippet}\n\ninstruction: Based on the title and description, write one sentence point about the article related to the tags. Mention something positive about the article and tags.\n\nmessage:"

    response = openai.Completion.create(
        engine="davinci",
        prompt=fewshots + prompt,
        temperature=0.7,
        max_tokens=150,
        stop=["--"],
    )
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return ""

    return response["choices"][0]["text"].strip()


def analyze_serp_article_sentiment(article_title: str, article_snippet: str):
    """Analyze the sentiment of an article using OpenAI's davinci-03 API.

    Args:
        article_title (str): The title of the article.
        article_snippet (str): The snippet of the article.

    Returns:
        dict: Dictionary of sentiment analysis results.
    """
    instruction = "Is this article 'positive' or 'negative' sentiment based on the title and snippet?"
    prompt = f"title: {article_title}\nsnippet: {article_snippet}\ninstruction: {instruction}\nsentiment:"
    response = wrapped_create_completion(
        model=CURRENT_OPENAI_DAVINCI_MODEL, prompt=prompt, max_tokens=1
    )

    return response.lower()
