import requests
import os
from model_import import Prospect, ClientSDR
from app import db, celery
import time

from src.email_outbound.email_store.services import (
    create_email_store,
    email_store_hunter_verify,
)
from src.utils.slack import URL_MAP, send_slack_message

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY")
DEFAULT_MONTHLY_EMAIL_FETCHING_CREDITS = (
    2000  # number of email credits each sdr has per month
)


def get_email_from_hunter(
    first_name: str, last_name: str, company_website: str = "", company_name: str = ""
):
    # Retrieve a potential email
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


def verify_email_from_hunter(email_address: str) -> (bool, dict):
    """Calls the Hunter verify endpoint on an email address.

    Args:
        email_address (str): Email address to verify

    Returns:
        (bool, dict): (success, data)
    """
    # Get the email verifier payload
    url = "https://api.hunter.io/v2/email-verifier?email={email}&api_key={api_key}".format(
        email=email_address,
        api_key=HUNTER_API_KEY,
    )
    response = requests.get(url)
    if response.status_code != 200:
        return False, {"error": response.text}

    return True, response.json()


@celery.task
def find_hunter_email_from_prospect_id(
    prospect_id: int, trigger_from: str = "manually triggered"
):
    from src.email_classifier.services import verify_email

    p: Prospect = Prospect.query.get(prospect_id)
    print("\nProcessesing prospect: ", p.id)

    if not p or p.email:
        return None
    first_name = p.first_name
    last_name = p.last_name
    company_website = p.company_url
    company_name = p.company
    client_sdr_id = p.client_sdr_id

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not p.company_url or "linkedin.com/" in p.company_url:
        return None

    # Get the email
    success, data = get_email_from_hunter(
        first_name=first_name,
        last_name=last_name,
        company_website=company_website,
        company_name=company_name,
    )
    if not success:
        print(data)
        return None
    email = data["email"]
    score = data["score"]

    # Verify the email
    # success, email, _score = verify_email(email)
    # if not success:
    #     return None

    p.email = email
    p.email_score = score
    p.valid_primary_email = True
    p_id = p.id
    full_name = p.full_name
    overall_status = p.overall_status.value

    # Verify the email
    print("Verifying email: ", email)
    if email:
        email_store_id = create_email_store(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
        )
        p.email_store_id = email_store_id
        email_store_hunter_verify.delay(email_store_id=email_store_id)

    client_sdr_id = p.client_sdr_id
    db.session.add(p)
    db.session.commit()

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sdr.email_fetching_credits = client_sdr.email_fetching_credits - 1
    db.session.add(client_sdr)
    db.session.commit()

    send_slack_message(
        "🦊 Found email for {name} (#{id}) - {overall_status}\n{email} - Score: {score}\nTriggered reason: {trigger_from}".format(
            name=str(full_name),
            id=str(p_id),
            email=str(email),
            score=str(score),
            overall_status=str(overall_status),
            trigger_from=trigger_from,
        ),
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    return p


@celery.task(bind=True, max_retries=3)
def find_hunter_emails_for_prospects_under_archetype(
    self, client_sdr_id: int, archetype_id: int
) -> bool:
    """Finds hunter emails for all prospects under an archetype

    Args:
        archetype_id (int): archetype id

    Returns:
        bool: True
    """
    prospects: list = Prospect.query.filter_by(
        client_sdr_id=client_sdr_id, archetype_id=archetype_id, email=None
    ).all()

    count = 0
    for prospect in prospects:
        count += 1
        if count % 5 == 0:
            time.sleep(1)
        p_id: int = prospect.id
        find_hunter_email_from_prospect_id.delay(p_id)

    return True


def replenish_all_email_credits_for_all_sdrs():
    client_sdrs: list = ClientSDR.query.all()
    for sdr in client_sdrs:
        sdr.email_fetching_credits = DEFAULT_MONTHLY_EMAIL_FETCHING_CREDITS
        db.session.add(sdr)
        db.session.commit()
