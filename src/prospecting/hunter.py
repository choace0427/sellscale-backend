import requests
import os
from model_import import Prospect
from app import db, celery

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY")


def get_email_from_hunter(
    first_name: str, last_name: str, company_website: str = "", company_name: str = ""
):
    url = "https://api.hunter.io/v2/email-finder?domain={domain}&first_name={first_name}&last_name={last_name}&api_key={api_key}&company={company}".format(
        domain=company_website,
        first_name=first_name,
        last_name=last_name,
        company=company_name,
        api_key=HUNTER_API_KEY,
    )
    response = requests.get(url)
    if response.status_code != 200:
        return False, {"error": response.text}
    return True, {
        "email": response.json()["data"]["email"],
        "score": response.json()["data"]["score"],
        "respose": response.json(),
    }


@celery.task
def find_hunter_email_from_prospect_id(prospect_id: int):
    p: Prospect = Prospect.query.get(prospect_id)
    if not p or p.email:
        return None
    first_name = p.first_name
    last_name = p.last_name
    company_website = p.company_url
    company_name = p.company

    if "linkedin.com/" in p.company_url:
        return None

    success, data = get_email_from_hunter(
        first_name=first_name,
        last_name=last_name,
        company_website=company_website,
        company_name=company_name,
    )
    if not success:
        return None

    email = data["email"]
    score = data["score"]
    p.email = email
    p.hunter_email_score = score
    db.session.add(p)
    db.session.commit()
    return p
