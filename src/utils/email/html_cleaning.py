import re
from typing import Optional
from bs4 import BeautifulSoup


def clean_html(html: str, remove_past_convo: Optional[bool] = False) -> str:
    """Takes a string of HTML and returns a cleaned version of it. Tags removed.

    Args:
        html (str): HTML string to be cleaned
        remove_past_convo (Optional[bool], optional): Whether to remove past conversations. Defaults to False.

    Returns:
        str: Cleaned HTML string
    """
    # Convert <br> into newlines and remove duplicate newlines
    html = html.replace("<br>", "\n")
    html = re.sub(r"\n+", "\n", html)
    soup = BeautifulSoup(html, "html.parser")

    if remove_past_convo:
        # Remove past conversations
        for div in soup.find_all("div", {"class": "gmail_quote"}):
            div.decompose()

    # Convert <br> into newlines and remove duplicate newlines
    souped = soup.get_text()
    souped = souped.replace("<br>", "\n")
    souped = re.sub(r"\n+", "\n", souped)

    return souped
