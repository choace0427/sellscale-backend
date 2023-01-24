from app import db, celery
from src.prospecting.models import ProspectUploadsRawCSV, ProspectUploads, ProspectUploadsStatus, ProspectUploadsErrorType
from src.prospecting.services import create_prospect_from_linkedin_link
import json, hashlib


def create_raw_csv_entry_from_json_payload(
        client_id: int,
        client_archetype_id: int,
        client_sdr_id: int,
        payload: list[dict]) -> int:
    """ Create a raw CSV entry from the JSON payload sent by the SDR.

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
        client_id = client_id,
        client_archetype_id = client_archetype_id,
        client_sdr_id = client_sdr_id,
        csv_data_hash = payload_hash_value
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
        payload: dict) -> bool:
    """ Populate the ProspectUploads table from the JSON payload sent by the SDR.

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
        exists = ProspectUploads.query.filter_by(               # Check for duplicates
            client_id = client_id,
            client_archetype_id = client_archetype_id,
            client_sdr_id = client_sdr_id,
            csv_row_hash = prospect_hash_value
        ).first()
        if exists:
            status = ProspectUploadsStatus.DISQUALIFIED         # If duplicate, mark as disqualified
            error_type = ProspectUploadsErrorType.DUPLICATE

        prospect_upload: ProspectUploads = ProspectUploads(
            client_id=client_id,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            prospect_uploads_raw_csv_id=prospect_uploads_raw_csv_id,
            csv_row_data = prospect,
            csv_row_hash = prospect_hash_value,
            upload_attempts = 0,
            status = status,
            error_type = error_type,
            iscraper_error_message = None,
        )
        prospect_uploads.append(prospect_upload)

    db.session.bulk_save_objects(prospect_uploads)
    db.session.commit()

    return True


def run_celery_jobs_for_upload(client_id: int, client_archetype_id: int, client_sdr_id: int) -> bool:
    """ Collects the rows eligible for upload and runs the celery jobs for them.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.

    Returns:
        bool: True if the celery jobs were run successfully. Errors otherwise.
    """
    eligible_rows: ProspectUploads = ProspectUploads.query.filter_by(           # Get all eligible rows (only on UPLOAD_NOT_STARTED and UPLOAD_FAILED)   
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        status=(ProspectUploadsStatus.UPLOAD_NOT_STARTED, ProspectUploadsStatus.UPLOAD_FAILED)
    ).all()

    for row in eligible_rows:
        row: ProspectUploads = row
        prospect_row_id = row.id
        prospect_upload: ProspectUploads = ProspectUploads.query.get(id=prospect_row_id)
        if prospect_upload:
            prospect_upload.status = ProspectUploadsStatus.UPLOAD_QUEUED
            db.session.add(prospect_upload)
            db.session.commit()
            
            # create_prospect_from_prospect_upload_row.apply_async(prospect_row_id)
    
    return True


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_prospect_upload_row(self, prospect_upload_id: int) -> bool:
    try:
        prospect_upload: ProspectUploads = ProspectUploads.query.get(id=prospect_upload_id)
        if not prospect_upload:
            return False

        prospect_upload.upload_attempts += 1
        prospect_upload.status = ProspectUploadsStatus.UPLOAD_IN_PROGRESS
        db.session.add(prospect_upload)
        db.session.commit()

        # Create the prospect.
        #  linkedin_url = prospect_upload.csv_row_data.get("linkedin_url")
        # created = create_prospect_from_linkedin_link.delay(
        #     archetype_id=prospect_upload.client_archetype_id,
        #     linkedin_url=linkedin_url)

        # if created:
        #     prospect_upload.status = ProspectUploadsStatus.UPLOAD_SUCCESS
        #     db.session.add(prospect_upload)
        #     db.session.commit()
        #     return True

        # TODO: Override ^ Create prospect from linkedin link :')

    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)
