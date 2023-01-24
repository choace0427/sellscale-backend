from app import db, celery
from src.prospecting.models import ProspectUploadsRawCSV, ProspectUploads, ProspectUploadsStatus, ProspectUploadsErrorType
from model_import import Client, ClientArchetype
from src.prospecting.services import get_linkedin_slug_from_url, get_navigator_slug_from_url, add_prospect
from src.research.linkedin.services import research_personal_profile_details, get_iscraper_payload_error
from src.utils.abstract.attr_utils import deep_get
from typing import Optional
import json, hashlib

from src.utils.slack import send_slack_message, URL_MAP
ENG_SANDBOX = [URL_MAP.get("eng-sandbox")]



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

    prospect_uploads = []
    for prospect in payload:
        prospect_hash_value = hashlib.sha256(json.dumps(prospect).encode()).hexdigest()
        status = ProspectUploadsStatus.UPLOAD_NOT_STARTED
        error_type = None
        exists = ProspectUploads.query.filter_by(  # Check for duplicates
            client_id=client_id,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            csv_row_hash=prospect_hash_value,
        ).first()
        if exists:
            status = (
                ProspectUploadsStatus.DISQUALIFIED
            )  # If duplicate, mark as disqualified
            error_type = ProspectUploadsErrorType.DUPLICATE

        prospect_upload: ProspectUploads = ProspectUploads(
            client_id=client_id,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            prospect_uploads_raw_csv_id=prospect_uploads_raw_csv_id,
            csv_row_data=prospect,
            csv_row_hash=prospect_hash_value,
            upload_attempts=0,
            status=status,
            error_type=error_type,
            iscraper_error_message=None,
        )
        prospect_uploads.append(prospect_upload)

    db.session.bulk_save_objects(prospect_uploads)
    db.session.commit()

    return True


def collect_and_run_celery_jobs_for_upload(client_id: int, client_archetype_id: int, client_sdr_id: int) -> bool:
    """ Collects the rows eligible for upload and runs the celery jobs for them.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.

    Returns:
        bool: True if the celery jobs were collected and scheduled successfully. Errors otherwise.
    """
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
            send_slack_message("Prospect upload queued for row ID: " + str(prospect_upload.id), ENG_SANDBOX)
            create_prospect_from_prospect_upload_row.delay(prospect_upload_id = prospect_upload.id)
    
    return True


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
        send_slack_message("create_prospect_from_prosect_upload_row on: " + str(prospect_upload_id), ENG_SANDBOX)
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return

        # Create the prospect using the LinkedIn URL.
        create_prospect_from_linkedin_link.delay(
            prospect_upload_id=prospect_upload.client_archetype_id,
        )

        # Future ways to create the prospect can go below
        # HERE

    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_linkedin_link(self, prospect_upload_id: int, email: str = None) -> bool:
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
        send_slack_message("create_prospect_from_linkedin_link on: " + str(prospect_upload_id), ENG_SANDBOX)
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return False
        
        # Mark the prospect upload row as UPLOAD_IN_PROGRESS.
        prospect_upload.upload_attempts += 1
        prospect_upload.status = ProspectUploadsStatus.UPLOAD_IN_PROGRESS
        db.session.add(prospect_upload)
        db.session.commit()

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
        title = deep_get(iscraper_payload, "sub_title")
        twitter_url = None

        # Add prospect
        added = add_prospect(
            client_id=prospect_upload.client_id,
            archetype_id=prospect_upload.client_archetype_id,
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
        )
        if added:
            prospect_upload.status = ProspectUploadsStatus.UPLOAD_COMPLETE
            db.session.add(prospect_upload)
            db.session.commit()
            return True
        else:
            raise(Exception("Prospect could not be added."))
    except Exception as e:
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return False

        # Mark as Failed
        prospect_upload.status = ProspectUploadsStatus.UPLOAD_FAILED
        db.session.add(prospect_upload)
        db.session.commit()

        raise self.retry(exc=e, countdown=2**self.request.retries)

