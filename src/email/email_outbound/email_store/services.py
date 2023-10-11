from app import db, celery
from src.email.email_outbound.email_store.models import EmailStore, HunterVerifyStatus


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
def collect_and_trigger_email_store_hunter_verify(self) -> bool:
    """Collects all EmailStores with status PENDING and triggers an async task to verify them.

    Returns:
        bool: True
    """
    try:
        email_stores: list[EmailStore] = EmailStore.query.filter_by(verification_status_hunter=HunterVerifyStatus.PENDING).all()
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
    from src.email.email_outbound.email_store.hunter import verify_email_from_hunter

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
        email_store.verification_status_hunter_attempts = email_store.verification_status_hunter_attempts + 1
        email_store.verification_status_hunter_error = str(e)

        # If we've tried 3 times, mark as failed
        if email_store.verification_status_hunter_attempts >= 3:
            email_store.verification_status_hunter = HunterVerifyStatus.FAILED
        else:
            email_store.verification_status_hunter = HunterVerifyStatus.PENDING

        db.session.commit()
        self.retry(exc=e, countdown=60)
