from app import db, celery
from src.prospecting.models import ProspectUploadsRawCSV, ProspectUploads, ProspectUploadsStatus, ProspectUploadsErrorType, Prospect
from src.prospecting.services import get_linkedin_slug_from_url, get_navigator_slug_from_url, add_prospect
from src.research.linkedin.services import research_personal_profile_details, get_iscraper_payload_error
from src.utils.abstract.attr_utils import deep_get
from typing import Optional
from sqlalchemy import bindparam, update
import json, hashlib
import math


def create_raw_csv_entry_from_json_payload(
    client_id: int, client_archetype_id: int, client_sdr_id: int, payload: list
):
    """Create a raw CSV entry from the JSON payload sent by the SDR.

    We check the hash of the payload against payloads in the past. If the hash is the same, we return -1.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.
        payload (list[dict]): The payload sent by the SDR.

    Returns:
        int: The ID of the raw CSV entry. -1 if the hash already exists (duplicate payload).
    """

    # Hash the payload so we can check against duplicates.
    json_dumps = json.dumps(payload)
    payload_hash_value: str = hashlib.sha256(json_dumps.encode()).hexdigest()

    # Check if we already have this payload in the database.
    exists = ProspectUploadsRawCSV.query.filter_by(
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        csv_data_hash=payload_hash_value,
    ).first()
    if exists:
        return -1

    # Create a ProspectUploadsRawCSV entry using the payload as csv_data.
    raw_csv_entry: ProspectUploadsRawCSV = ProspectUploadsRawCSV(
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        csv_data=payload,
        csv_data_hash=payload_hash_value,
    )
    db.session.add(raw_csv_entry)
    db.session.commit()

    return raw_csv_entry.id


def populate_prospect_uploads_from_json_payload(
    client_id: int,
    client_archetype_id: int,
    client_sdr_id: int,
    prospect_uploads_raw_csv_id: int,
    payload: dict,
) -> bool:
    """Populate the ProspectUploads table from the JSON payload sent by the SDR.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.
        prospect_uploads_raw_csv_id (int): The ID of the ProspectUploadsRawCSV entry.
        payload (dict): The payload sent by the SDR.

    Returns:
        bool: True if the ProspectUploads table was populated successfully. Errors otherwise.
    """

    # Create prospect_list which preserves all rows from the payload.
    # prospect_list = [
    #   {"prospect_hash": "1234", "prospect": "something"},
    #   {"prospect_hash": "1234", "prospect": "something"}
    #   {"prospect_hash": "4321", "prospect": "not-something"}
    # ]
    # Create prospect_hashes which track unique hashes.
    # prospect_hashes = {"1234", "4321"}
    prospect_list = []
    prospect_hashes = []
    for prospect_row in payload:
        prospect_hash_value = hashlib.sha256(json.dumps(prospect_row).encode()).hexdigest()
        prospect_list.append({
            "prospect_hash": prospect_hash_value,
            "prospect_data": prospect_row,
        })
        prospect_hashes.append(prospect_hash_value)

    # Get ProspectUploads that match the prospect_hashes, and create a set off the existent hashes.
    existing_prospect_uploads = ProspectUploads.query.filter(
        ProspectUploads.client_id == client_id,
        ProspectUploads.client_archetype_id == client_archetype_id,
        ProspectUploads.client_sdr_id == client_sdr_id,
        ProspectUploads.csv_row_hash.in_(prospect_hashes)
    ).all()
    existing_prospect_hash = set()
    for existing_prospect_upload in existing_prospect_uploads:
        existing_prospect_hash.add(existing_prospect_upload.csv_row_hash)


    # Create ProspectUploads
    prospect_uploads = []
    for prospect_dic in prospect_list:
        status = ProspectUploadsStatus.UPLOAD_NOT_STARTED
        error_type = None
        if prospect_dic["prospect_hash"] in existing_prospect_hash:
            status = ProspectUploadsStatus.DISQUALIFIED  # If duplicate, mark as disqualified
            error_type = ProspectUploadsErrorType.DUPLICATE

        prospect_upload = ProspectUploads(
            client_id=client_id,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            prospect_uploads_raw_csv_id=prospect_uploads_raw_csv_id,
            csv_row_data=prospect_dic["prospect_data"],
            csv_row_hash=prospect_dic["prospect_hash"],
            upload_attempts=0,
            status=status,
            error_type=error_type,
            iscraper_error_message=None,
        )
        prospect_uploads.append(prospect_upload)

    db.session.bulk_save_objects(prospect_uploads)
    db.session.commit()

    return True

@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def collect_and_run_celery_jobs_for_upload(self, client_id: int, client_archetype_id: int, client_sdr_id: int) -> bool:
    """ Collects the rows eligible for upload and runs the celery jobs for them.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.

    Returns:
        bool: True if the celery jobs were collected and scheduled successfully. Errors otherwise.
    """
    try:
        not_started_rows: ProspectUploads = ProspectUploads.query.filter_by(             # Get all not_started rows
            client_id=client_id,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            status=ProspectUploadsStatus.UPLOAD_NOT_STARTED,
        ).all()
        failed_rows: ProspectUploads = ProspectUploads.query.filter_by(                  # Get all failed rows
            client_id=client_id,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            status=ProspectUploadsStatus.UPLOAD_FAILED,
        ).all()

        eligible_rows = not_started_rows + failed_rows
        for row in eligible_rows:
            row: ProspectUploads = row
            prospect_row_id = row.id
            prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_row_id)
            if prospect_upload:
                prospect_upload.status = ProspectUploadsStatus.UPLOAD_QUEUED
                db.session.add(prospect_upload)
                db.session.commit()
                create_prospect_from_prospect_upload_row.apply_async(args=[prospect_upload.id], queue="prospecting", routing_key="prospecting", priority=2)

        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)



@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_prospect_upload_row(self, prospect_upload_id: int) -> None:
    """Celery task for creating a prospect from a ProspectUploads row.

    This will call the create_prospect_from_linkedin_link function which will create the prospect.
    Space is left for future work to create prospects from other sources.

    Args:
        prospect_upload_id (int): The ID of the ProspectUploads row.

    Raises:
        self.retry: If the task fails, it will retry, up to the max_retries limit.

    Returns:
        None: Returns nothing.
    """
    try:
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return

        # Create the prospect using the LinkedIn URL.
        create_prospect_from_linkedin_link.apply_async(
            args=[prospect_upload.id], queue="prospecting", routing_key="prospecting", priority=2
        )

        # Future ways to create the prospect can go below
        # HERE

    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_linkedin_link(self, prospect_upload_id: int) -> bool:
    """ Celery task for creating a prospect from a LinkedIn URL.

    Args:
        prospect_upload_id (int): The ID of the ProspectUploads row.
        email (str, optional): An email to add to the prospect. Defaults to None.

    Raises:
        self.retry: If the task fails, it will retry, up to the max_retries limit.

    Returns:
        bool: True if the prospect was created successfully. Errors otherwise.
    """
    try:
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return False

        # Mark the prospect upload row as UPLOAD_IN_PROGRESS.
        prospect_upload.upload_attempts += 1
        prospect_upload.status = ProspectUploadsStatus.UPLOAD_IN_PROGRESS
        db.session.add(prospect_upload)
        db.session.commit()

        email = prospect_upload.csv_row_data.get("email", None)
        linkedin_url = prospect_upload.csv_row_data.get("linkedin_url")
        # Get the LinkedIn URL profile id for iScraper.
        if "/in/" in linkedin_url:
            slug = get_linkedin_slug_from_url(linkedin_url)
        elif "/lead/" in linkedin_url:
            slug = get_navigator_slug_from_url(linkedin_url)

        # Get the iScraper payload. If the payload has errors, mark the prospect upload row as UPLOAD_FAILED and STOP.
        iscraper_payload = research_personal_profile_details(profile_id=slug)
        if not deep_get(iscraper_payload, "first_name"):
            error = get_iscraper_payload_error(iscraper_payload)
            prospect_upload.status = ProspectUploadsStatus.DISQUALIFIED if error == "Profile data cannot be retrieved." else ProspectUploadsStatus.UPLOAD_FAILED
            prospect_upload.error_type = ProspectUploadsErrorType.ISCRAPER_FAILED
            prospect_upload.iscraper_error_message = error
            db.session.add(prospect_upload)
            db.session.commit()
            return False

        # Get Prospect fields - needs change in future
        company_name = deep_get(iscraper_payload, "position_groups.0.company.name")
        company_url = deep_get(iscraper_payload, "position_groups.0.company.url")
        employee_count = (
            str(deep_get(iscraper_payload, "position_groups.0.company.employees.start"))
            + "-"
            + str(deep_get(iscraper_payload, "position_groups.0.company.employees.end"))
        )
        full_name = (deep_get(iscraper_payload, "first_name") + " " + deep_get(iscraper_payload, "last_name"))
        industry = deep_get(iscraper_payload, "industry")
        linkedin_url = "linkedin.com/in/{}".format(deep_get(iscraper_payload, "profile_id"))
        linkedin_bio = deep_get(iscraper_payload, "summary")
        title = deep_get(iscraper_payload, "position_groups.0.profile_positions.0.title") or deep_get(iscraper_payload, "sub_title")
        twitter_url = None

        # Health Check fields
        followers_count = deep_get(iscraper_payload, "network_info.followers_count") or 0

        # Add prospect
        added = add_prospect(
            client_id=prospect_upload.client_id,
            archetype_id=prospect_upload.client_archetype_id,
            client_sdr_id=prospect_upload.client_sdr_id,
            company=company_name,
            company_url=company_url,
            employee_count=employee_count,
            full_name=full_name,
            industry=industry,
            linkedin_url=linkedin_url,
            linkedin_bio=linkedin_bio,
            title=title,
            twitter_url=twitter_url,
            email=email,
            linkedin_num_followers=followers_count,
        )
        if added:
            prospect_upload.status = ProspectUploadsStatus.UPLOAD_COMPLETE
            db.session.add(prospect_upload)
            db.session.commit()
            return True
        else:
            prospect_upload.status = ProspectUploadsStatus.DISQUALIFIED
            prospect_upload.error_type = ProspectUploadsErrorType.DUPLICATE
            db.session.add(prospect_upload)
            db.session.commit()
            return False
    except Exception as e:
        db.session.rollback()
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return False

        # Mark as Failed
        prospect_upload.status = ProspectUploadsStatus.UPLOAD_FAILED
        db.session.add(prospect_upload)
        db.session.commit()

        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def run_and_assign_health_score(self, archetype_id: int):
    """ Celery task for running and assigning health scores to prospects.

    Only runs on prospects that have not been assigned a health score.

    Args:
        archetype_id (int): The archetype id to run the health score on.

    Raises:
        self.retry: If the task fails, it will retry, up to the max_retries limit.
    """
    # Get the prospects for the archetype
    try:
        prospects: list[Prospect] = Prospect.query.filter_by(
            archetype_id=archetype_id,
            health_check_score=None,
        ).all()

        update_prospects: list[dict] = []
        for p in prospects:
            if p.li_num_followers is None:      # This should only happen on existent records, iScraper won't give None here.
                continue

            health_score = 0

            if p.linkedin_bio is not None and len(p.linkedin_bio) > 0:
                health_score += 25

            # Calculate score based off of Sigmoid Function (using follower count)
            sig_score = calculate_health_check_follower_sigmoid(p.li_num_followers or 0)
            health_score += sig_score

            update_prospects.append({
                "p_id": p.id,
                "health_score": health_score
            })

        # UPDATE prospect WHERE id = :id SET health_check_score = :health_score
        stmt = (
            update(Prospect)
            .where(Prospect.id == bindparam("p_id"))
            .values(health_check_score=bindparam("health_score"))
        )
        db.session.execute(stmt, update_prospects)
        db.session.commit()

        return True, "Successfully calculated health check scores for archetype: {}".format(archetype_id)
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def calculate_health_check_follower_sigmoid(num_followers: int = 0) -> int:
    """Calculates a health check score for a prospect based on their number of followers.

    Uses a sigmoid function to calculate a score between 0 and 75.

    Args:
        num_followers (int): The number of followers a prospect has on LinkedIn.

    Returns:
        int: A score between 0 and 75.
    """
    k = 0.015           # Sigmoid function constant
    midpoint = 300      # Sigmoid function midpoint
    upper_bound = 75    # Sigmoid function upper bound
    raw_sig_score = upper_bound / (1 + math.exp(-k * (num_followers - midpoint)))
    y_intercept_adjuster = upper_bound / (1 + math.exp(k * midpoint))
    sig_score = raw_sig_score - y_intercept_adjuster

    return sig_score


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def refresh_bio_followers_for_prospect(self, prospect_id: int):
	try:
		p = Prospect.query.get(prospect_id)
		print(p)
		li_slug = get_linkedin_slug_from_url(p.linkedin_url)
		scraper_payload = research_personal_profile_details(li_slug)
		if not deep_get(scraper_payload, "first_name"):
			return ('scraper_error', scraper_payload)

		linkedin_bio = deep_get(scraper_payload, "summary")
		followers_count = deep_get(scraper_payload, "network_info.followers_count") or 0

		p.linkedin_bio = linkedin_bio
		p.li_num_followers = followers_count

		db.session.add(p)
		db.session.commit()

		return True
	except Exception as e:
		db.session.rollback()
		raise self.retry(exc=e, countdown=2**self.request.retries)