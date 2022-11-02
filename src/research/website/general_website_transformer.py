import requests
import json
import pandas
import urllib.request
from bs4 import BeautifulSoup
import re
import random

from src.ml.fine_tuned_models import get_basic_openai_completion


def find_points_from_website(url):
    if not url:
        return None

    fp = urllib.request.urlopen(url)
    mybytes = fp.read()

    mystr = mybytes.decode("utf8")
    fp.close()

    c = []

    words_re = re.compile(
        "|".join(
            [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "direction",
                "location",
                "disclaimer",
                "contact us",
                "location",
                "phone",
                "copyright",
                "located",
                "get started",
                "careers",
                "products",
                "company",
                "search",
                "learn more",
                "policy",
                "newsroom",
                "our policy",
                "close menu",
                "shop",
                "read more",
                "see overview",
                "news",
                "see all",
            ]
        )
    )

    soup = BeautifulSoup(mystr, "html.parser")
    ps = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "div"])
    for p in ps:
        if len(p.get_text()) > 0:
            contents = p.get_text().replace("\n", ".")
            contents = re.sub("[^A-Za-z0-9\.']+", " ", p.get_text())
            if (
                "<" not in contents
                and len(contents) > 150
                and not words_re.search(contents.lower())
            ):
                contents = contents.replace("\xa0", " ")
                contents = contents.strip()
                c.append(contents)

    return [random.choice(c)]


def generate_simple_summary(prompt):
    prompt_frame = """prompt: Holiday gift guide Celebrate the joy of the season with amazing tech gifts. Shop and ship early for holiday delivery. Holiday gift guide Celebrate the joy of the season with amazing tech gifts. Shop and ship early for holiday delivery. Shop
summary: I saw your website and noticed you all have started promoting a bunch of amazing tech gifts.XXX

prompt: Your next best revenue channel Engage your customers through SMS marketing. It s easy. It works. We're at your service. Book a demo 1 click set up 30 day free trial 5x ROI guarantee based on reviews on
summary: I saw your website and noticed how you highlight yourself as the best revenue channel for SMS Marketing.XXX

prompt: Whether you are buying a server for the first time or replacing an outdated model there is much to consider. With this server buying guide we ll walk you through everything you need to know to find the best server for small business.
summary: I saw your website and saw the server buying guide for small businesses.XXX

prompt: {}
summary:""".format(
        prompt
    )

    completion = get_basic_openai_completion(prompt_frame, max_tokens=25)
    return completion


def generate_general_website_research_points(url):
    point = find_points_from_website(url)
    prompt = "prompt: {}\nsummary: ".format(point)
    completion = generate_simple_summary(prompt)
    response = completion[0]
    return {"raw_data": {"url": url}, "prompt": "", "response": response}
