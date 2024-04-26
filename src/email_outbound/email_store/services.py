import time
from app import db, celery
from src.client.models import ClientSDR
from src.email_outbound.email_store.models import EmailStore, HunterVerifyStatus
from src.prospecting.models import Prospect
from src.utils.slack import URL_MAP, send_slack_message


def create_email_store(
    email: str,
    first_name: str,
    last_name: str,
    company_name: str,
) -> int:
    """Create a new EmailStore record. Sets the Hunter Verify status to PENDING.

    Args:
        email (str): _description_
        first_name (str): _description_
        last_name (str): _description_
        company_name (str): _description_

    Returns:
        int: _description_
    """
    # Make sure we aren't creating duplicates
    email_store: EmailStore = EmailStore.query.filter_by(email=email).first()
    if email_store:
        return email_store.id

    email_store = EmailStore(
        email=email,
        first_name=first_name,
        last_name=last_name,
        company_name=company_name,
        verification_status_hunter=HunterVerifyStatus.PENDING,
    )
    db.session.add(email_store)
    db.session.commit()

    return email_store.id


@celery.task(bind=True, max_retries=3)
def find_emails_for_archetype(self, archetype_id: int) -> bool:
    """Finds emails for all prospects under an archetype that don't have emails.

    Args:
        archetype_id (int): archetype id

    Returns:
        bool: True
    """
    prospects: list[Prospect] = Prospect.query.filter_by(
        archetype_id=archetype_id,
        email=None,
    ).all()

    from src.automation.orchestrator import add_process_list

    add_process_list(
        type="find_email_for_prospect_id",
        args_list=[{"prospect_id": prospect.id} for prospect in prospects],
        chunk_size=50,
        chunk_wait_minutes=1,
    )
    return True


@celery.task(bind=True, max_retries=3)
def find_email_for_prospect_id(self, prospect_id: int) -> str:
    """Finds an email for a prospect using DataGMA, FindyMail, and Hunter.

    Args:
        prospect_id (int): ID of the prospect to find an email for

    Returns:
        str: The email address found
    """
    email = None
    found = False
    verified = False

    # Get the prospect
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None

    # Get the prospect's name and company
    name = prospect.full_name
    company = prospect.company

    # Source 1: DataGMA
    try:
        from src.email_outbound.email_store.datagma import DataGMA

        datagma = DataGMA()
        datagma_email = datagma.find_from_name_and_company(name=name, company=company)
        if datagma_email:
            email = datagma_email.get("email")
            if email and "," not in email:
                email = email
                found = True
                if datagma_email.get("status") == "Valid":
                    verified = True
    except:
        pass

    # Source 2: FindyMail
    # Note: There are only 300 active concurrent requests allowed.
    # If we ever scale to a point where we have more than 300 concurrent requests, we'll need to
    # implement a queue.
    if not found:
        try:
            from src.email_outbound.email_store.findymail import FindyMail

            findymail = FindyMail()
            findymail_email = findymail.find_from_name_and_company(
                name=name, company=company
            )
            if findymail_email:
                contact = findymail_email.get("contact")
                if contact:
                    email = contact.get("email")
                    if email and "," not in email:
                        email = email
                        found = True
        except:
            pass

    # Source 3: Hunter
    if not found:
        try:
            from src.email_outbound.email_store.hunter import get_email_from_hunter

            success, data = get_email_from_hunter(
                first_name=prospect.first_name,
                last_name=prospect.last_name,
                company_website=prospect.company_url,
                company_name=company,
            )
            if success:
                email = data["email"]
                if email and "," not in email:
                    email = email
                    found = True
        except:
            pass

    # If no email found, return None
    if not email or not found:
        return None

    # Verify the email
    from src.email_classifier.services import verify_email

    if not verified:
        success, email, score = verify_email(email=email)
        if not success:
            return None
    else:
        success, email, score = (
            True,
            email,
            0.99,
        )  # If the email was already verified, we'll assume it's a good email

    # Update the prospect
    prospect.email = email
    prospect.email_score = score
    prospect.valid_primary_email = True
    db.session.commit()

    # Create an EmailStore
    email_store_id = create_email_store(
        email=email,
        first_name=prospect.first_name,
        last_name=prospect.last_name,
        company_name=company,
    )
    prospect.email_store_id = email_store_id
    email_store_hunter_verify.delay(email_store_id=email_store_id)

    # Deduct credits from the Client SDR
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client_sdr.email_fetching_credits = client_sdr.email_fetching_credits - 1
    db.session.commit()

    # Send a Slack message
    send_slack_message(
        "🦊 Found email for {name} (#{id}) - {overall_status}\n{email} - Score: {score}".format(
            name=str(prospect.full_name),
            id=str(prospect.id),
            email=str(email),
            score=str(score),
            overall_status=str(prospect.overall_status.value),
        ),
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    return email


@celery.task(bind=True, max_retries=3)
def collect_and_trigger_email_store_hunter_verify(self) -> bool:
    """Collects all EmailStores with status PENDING and triggers an async task to verify them.

    Returns:
        bool: True
    """
    try:
        email_stores: list[EmailStore] = EmailStore.query.filter_by(
            verification_status_hunter=HunterVerifyStatus.PENDING
        ).all()
        for email_store in email_stores:
            email_store_hunter_verify.delay(email_store.id)

        return True
    except Exception as e:
        self.retry(exc=e, countdown=60)


@celery.task(bind=True, max_retries=3)
def email_store_hunter_verify(self, email_store_id: int) -> (bool, str):
    """Runs Hunter verify endpoint on an EmailStore, if the verification status is PENDING.

    Args:
        email_store_id (int): ID of the EmailStore to verify

    Returns:
        (bool, str): (success, message)
    """
    from src.email_outbound.email_store.hunter import verify_email_from_hunter

    try:
        email_store: EmailStore = EmailStore.query.get(email_store_id)
        if email_store.verification_status_hunter != HunterVerifyStatus.PENDING:
            return False, "EmailStore is not pending verification"

        # Mark as in progress
        email_store.verification_status_hunter = HunterVerifyStatus.IN_PROGRESS
        db.session.commit()

        # Run Hunter verify
        email_store: EmailStore = EmailStore.query.get(email_store_id)
        email_address = email_store.email
        success, data = verify_email_from_hunter(email_address)

        # If not success
        if not success:
            raise Exception(data)
        data = data["data"]

        # Update the EmailStore
        email_store: EmailStore = EmailStore.query.get(email_store_id)
        email_store.hunter_status = data["status"]
        email_store.hunter_score = data["score"]
        email_store.hunter_regexp = data["regexp"]
        email_store.hunter_gibberish = data["gibberish"]
        email_store.hunter_disposable = data["disposable"]
        email_store.hunter_webmail = data["webmail"]
        email_store.hunter_mx_records = data["mx_records"]
        email_store.hunter_smtp_server = data["smtp_server"]
        email_store.hunter_smtp_check = data["smtp_check"]
        email_store.hunter_accept_all = data["accept_all"]
        email_store.hunter_block = data["block"]
        email_store.hunter_sources = data["sources"]

        # Mark as complete
        email_store.verification_status_hunter = HunterVerifyStatus.COMPLETE
        email_store.verification_status_hunter_error = None
        db.session.commit()

        return True, "Success"
    except Exception as e:
        email_store: EmailStore = EmailStore.query.get(email_store_id)
        email_store.verification_status_hunter = HunterVerifyStatus.FAILED
        email_store.verification_status_hunter_attempts = (
            email_store.verification_status_hunter_attempts + 1
        )
        email_store.verification_status_hunter_error = str(e)

        # If we've tried 3 times, mark as failed
        if email_store.verification_status_hunter_attempts >= 3:
            email_store.verification_status_hunter = HunterVerifyStatus.FAILED
        else:
            email_store.verification_status_hunter = HunterVerifyStatus.PENDING

        db.session.commit()
        self.retry(exc=e, countdown=60)
