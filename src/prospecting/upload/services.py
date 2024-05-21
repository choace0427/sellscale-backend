from src.client.models import ClientArchetype, ClientSDR
from src.automation.li_searcher import search_for_li
from app import db, celery
from src.prospecting.icp_score.services import apply_icp_scoring_ruleset_filters_task
from src.prospecting.champions.services import mark_prospects_as_champion
from src.prospecting.models import (
    ProspectUploadHistory,
    ProspectUploadHistoryStatus,
    ProspectUploadSource,
    ProspectUploadsRawCSV,
    ProspectUploads,
    ProspectUploadsStatus,
    ProspectUploadsErrorType,
    Prospect,
)
from src.prospecting.services import (
    get_linkedin_slug_from_url,
    get_navigator_slug_from_url,
    add_prospect,
)
from src.research.account_research import generate_prospect_research
from src.research.models import IScraperPayloadType
from src.research.services import (
    create_custom_research_point_type,
    create_iscraper_payload_cache,
)
from sqlalchemy.orm.attributes import flag_modified
from src.segment.models import Segment
from src.segment.services import get_base_segment_for_archetype
from src.utils.abstract.attr_utils import deep_get
from typing import Optional, Union
from sqlalchemy import bindparam, update
import json, hashlib
import math


def get_prospect_upload_history(
    client_sdr_id: int,
    offset: int = 0,
    limit: int = 10,
) -> list[dict]:
    """Get the ProspectUploadHistory for a Client SDR. Paginated.

    Args:
        client_sdr_id (int): The client SDR ID.
        offset (int): The offset for the query. Defaults to 0.
        limit (int): The limit for the query. Defaults to 10.

    Returns:
        list[dict]: A list of ProspectUploadHistory entries.
    """
    upload_histories: list[ProspectUploadHistory] = (
        ProspectUploadHistory.query.filter_by(client_sdr_id=client_sdr_id)
        .order_by(ProspectUploadHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [upload_history.to_dict() for upload_history in upload_histories]


def get_prospect_upload_history_details(
    upload_id: int,
) -> dict:
    """Get the breakdown of a ProspectUploadHistory entry.

    Args:
        upload_id (int): The ID of the ProspectUploadHistory entry.

    Returns:
        dict: The details of the ProspectUploadHistory entry.
    """
    upload_history: ProspectUploadHistory = ProspectUploadHistory.query.get(upload_id)
    if not upload_history:
        return {}

    prospect_uploads: list[ProspectUploads] = ProspectUploads.query.filter_by(
        prospect_upload_history_id=upload_id
    ).all()

    return {
        "uploads": [prospect_upload.to_dict() for prospect_upload in prospect_uploads],
    }


def create_prospect_upload_history(
    client_id: int,
    client_sdr_id: int,
    upload_source: ProspectUploadSource,
    raw_data: dict,
    client_segment_id: int,
    client_archetype_id: Optional[int] = None,
) -> int:
    """Create a ProspectUploadHistory entry.

    Args:
        client_id (int): The client ID.
        client_sdr_id (int): The client SDR ID.
        upload_source (ProspectUploadSource): The source of the upload.
        raw_data (dict): The raw data to upload.
        client_segment_id (int): The client segment ID.
        client_archetype_id (int): The client archetype ID. Defaults to None.

    Returns:
        int: The ID of the ProspectUploadHistory entry.
    """
    # Determine the upload size and hash the raw data.
    upload_size = len(raw_data)
    raw_data_hash = hashlib.sha256(json.dumps(raw_data).encode()).hexdigest()

    # Check if we've already uploaded this data before.
    exists = ProspectUploadHistory.query.filter_by(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        upload_source=upload_source,
        raw_data_hash=raw_data_hash,
    ).first()
    if exists:
        return exists.id

    # Get the upload name by referencing the Segment and # of uploads under this segment
    segment: Segment = Segment.query.get(client_segment_id)
    
    past_uploads: int = ProspectUploadHistory.query.filter_by(
        client_segment_id=client_segment_id,
    ).count()
    
    if segment:
        upload_name = f"{segment.segment_title} #{past_uploads + 1}"
    else:
        upload_name = f"Segment {client_segment_id} #{past_uploads + 1}"

    prospect_upload_history: ProspectUploadHistory = ProspectUploadHistory(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        upload_name=upload_name,
        upload_size=upload_size,
        uploads_completed=0,
        uploads_not_started=upload_size,
        uploads_in_progress=0,
        uploads_failed=0,
        uploads_other=0,
        upload_source=upload_source,
        status=ProspectUploadHistoryStatus.UPLOAD_IN_PROGRESS,
        client_archetype_id=client_archetype_id,
        client_segment_id=client_segment_id,
        raw_data=raw_data,
        raw_data_hash=raw_data_hash,
    )
    db.session.add(prospect_upload_history)
    db.session.commit()

    return prospect_upload_history.id


@celery.task
def refresh_prospect_upload_history(
    prospect_upload_history_id: int,
    retry: bool = False,
) -> tuple[bool, str]:
    """Refreshes the ProspectUploadHistory entry.

    Args:
        prospect_upload_history_id (int): The ID of the ProspectUploadHistory entry.
        retry (bool): Whether or not to retry the refresh. Defaults to False.

    Returns:
        tuple[bool, str]: True if the refresh was successful, error message otherwise.
    """
    prospect_upload_history: ProspectUploadHistory = ProspectUploadHistory.query.get(
        prospect_upload_history_id
    )
    if not prospect_upload_history:
        return True, "ProspectUploadHistory entry not found."

    # Update the status
    status: ProspectUploadHistoryStatus = prospect_upload_history.update_status()

    # If the status is UPLOAD_COMPLETE, then we are done!
    if status == ProspectUploadHistoryStatus.UPLOAD_COMPLETE:
        return True, "ProspectUploadHistory entry updated successfully."
    else:  # Otherwise we need to wait another minute to check again
        if retry:
            from src.automation.orchestrator import add_process_for_future

            add_process_for_future(
                type="refresh_prospect_upload_history",
                args={
                    "prospect_upload_history_id": prospect_upload_history_id,
                    "retry": True,
                },
                minutes=1,  # 1 minute from now
            )
        return True, "ProspectUploadHistory entry still in progress."


def create_raw_csv_entry_from_json_payload(
    client_id: int,
    client_archetype_id: int,
    client_sdr_id: int,
    payload: list,
    allow_duplicates: bool = True,
):
    """Create a raw CSV entry from the JSON payload sent by the SDR.

    We check the hash of the payload against payloads in the past. If the hash is the same, we return -1.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.
        payload (list[dict]): The payload sent by the SDR.
        allow_duplicates (bool): Whether to check for duplicates. Defaults to True.

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
    if allow_duplicates and exists:
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


def populate_prospect_uploads_from_linkedin_link(
    upload_history_id: int,
) -> int:
    """Populate a single ProspectUploads entry from a LinkedIn URL.

    Args:
        upload_history_id (int): The ID of the ProspectUploadHistory entry.

    Returns:
        bool: True if the ProspectUploads entry was populated successfully. Errors otherwise.
    """
    upload_history: ProspectUploadHistory = ProspectUploadHistory.query.get(
        upload_history_id
    )
    data = upload_history.raw_data[0]
    data_hash = hashlib.sha256(json.dumps(data).encode()).hexdigest()
    prospect_upload: ProspectUploads = ProspectUploads(
        client_id=upload_history.client_id,
        client_archetype_id=upload_history.client_archetype_id,
        client_sdr_id=upload_history.client_sdr_id,
        prospect_upload_history_id=upload_history_id,
        upload_source=ProspectUploadSource.LINKEDIN_LINK,
        data=data,
        data_hash=data_hash,
        upload_attempts=0,
        status=ProspectUploadsStatus.UPLOAD_NOT_STARTED,
    )
    db.session.add(prospect_upload)
    db.session.commit()

    return prospect_upload.id


def populate_prospect_uploads_from_json_payload(
    client_id: int,
    client_archetype_id: int,
    client_sdr_id: int,
    prospect_uploads_raw_csv_id: int,
    prospect_upload_history_id: int,
    payload: dict,
    source: ProspectUploadSource,
    allow_duplicates: bool = True,
) -> bool:
    """Populate the ProspectUploads table from the JSON payload sent by the SDR.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.
        prospect_uploads_raw_csv_id (int): The ID of the ProspectUploadsRawCSV entry.
        payload (dict): The payload sent by the SDR.
        allow_duplicates (bool): Whether to check for duplicates. Defaults to True.

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
        prospect_hash_value = hashlib.sha256(
            json.dumps(prospect_row).encode()
        ).hexdigest()
        prospect_list.append(
            {
                "prospect_hash": prospect_hash_value,
                "prospect_data": prospect_row,
            }
        )
        prospect_hashes.append(prospect_hash_value)

    # Get ProspectUploads that match the prospect_hashes, and create a set off the existent hashes.
    existing_prospect_uploads = ProspectUploads.query.filter(
        ProspectUploads.client_id == client_id,
        ProspectUploads.client_archetype_id == client_archetype_id,
        ProspectUploads.client_sdr_id == client_sdr_id,
        ProspectUploads.data_hash.in_(prospect_hashes),
    ).all()
    existing_prospect_hash = set()
    if allow_duplicates:
        for existing_prospect_upload in existing_prospect_uploads:
            existing_prospect_hash.add(existing_prospect_upload.data_hash)

    # Create ProspectUploads
    prospect_uploads = []
    for prospect_dic in prospect_list:
        status = ProspectUploadsStatus.UPLOAD_NOT_STARTED
        error_type = None
        if prospect_dic["prospect_hash"] in existing_prospect_hash:
            status = (
                ProspectUploadsStatus.DISQUALIFIED
            )  # If duplicate, mark as disqualified
            error_type = ProspectUploadsErrorType.DUPLICATE

        prospect_upload = ProspectUploads(
            client_id=client_id,
            client_archetype_id=client_archetype_id,
            client_sdr_id=client_sdr_id,
            prospect_uploads_raw_csv_id=prospect_uploads_raw_csv_id,
            prospect_upload_history_id=prospect_upload_history_id,
            data=prospect_dic["prospect_data"],
            data_hash=prospect_dic["prospect_hash"],
            upload_source=source,
            upload_attempts=0,
            status=status,
            error_type=error_type,
            error_message=None,
        )
        prospect_uploads.append(prospect_upload)

    db.session.bulk_save_objects(prospect_uploads)
    db.session.commit()

    return True


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def collect_and_run_celery_jobs_for_upload(
    self,
    client_id: int,
    client_archetype_id: int,
    client_sdr_id: int,
    allow_duplicates: bool = True,
) -> bool:
    """Collects the rows eligible for upload and runs the celery jobs for them.

    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.
        allow_duplicates (bool): Whether to check for duplicates. Defaults to True.

    Returns:
        bool: True if the celery jobs were collected and scheduled successfully. Errors otherwise.
    """
    try:
        not_started_rows: ProspectUploads = (
            ProspectUploads.query.filter_by(  # Get all not_started rows
                client_id=client_id,
                client_archetype_id=client_archetype_id,
                client_sdr_id=client_sdr_id,
                status=ProspectUploadsStatus.UPLOAD_NOT_STARTED,
            ).all()
        )
        failed_rows: ProspectUploads = (
            ProspectUploads.query.filter_by(  # Get all failed rows
                client_id=client_id,
                client_archetype_id=client_archetype_id,
                client_sdr_id=client_sdr_id,
                status=ProspectUploadsStatus.UPLOAD_FAILED,
            ).all()
        )

        eligible_rows = not_started_rows + failed_rows
        for row in eligible_rows:
            row: ProspectUploads = row
            prospect_row_id = row.id
            prospect_upload: ProspectUploads = ProspectUploads.query.get(
                prospect_row_id
            )
            if prospect_upload:
                prospect_upload.status = ProspectUploadsStatus.UPLOAD_QUEUED
                db.session.add(prospect_upload)
                db.session.commit()
                create_prospect_from_prospect_upload_row.apply_async(
                    args=[prospect_upload.id, allow_duplicates],
                    queue="prospecting",
                    routing_key="prospecting",
                    priority=2,
                )

        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_prospect_upload_row(
    self,
    prospect_upload_id: int,
    allow_duplicates: bool = True,
) -> None:
    """Celery task for creating a prospect from a ProspectUploads row.

    This will call the create_prospect_from_linkedin_link function which will create the prospect.
    Space is left for future work to create prospects from other sources.

    Args:
        prospect_upload_id (int): The ID of the ProspectUploads row.
        allow_duplicates (bool): Whether to check for duplicates. Defaults to True.

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
            args=[prospect_upload.id, allow_duplicates],
            queue="prospecting",
            routing_key="prospecting",
            priority=2,
        )

        # Future ways to create the prospect can go below
        # HERE

    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_linkedin_link(
    self,
    prospect_upload_id: int,
    allow_duplicates: bool = True,
    mark_prospect_as_is_champion: bool = False,
) -> bool:
    """Celery task for creating a prospect from a LinkedIn URL.

    Args:
        prospect_upload_id (int): The ID of the ProspectUploads row.
        allow_duplicates (bool): Whether to check for duplicates. Defaults to True.

    Raises:
        self.retry: If the task fails, it will retry, up to the max_retries limit.

    Returns:
        bool: True if the prospect was created successfully. Errors otherwise.
    """
    from src.research.linkedin.services import (
        research_personal_profile_details,
        get_iscraper_payload_error,
        research_corporate_profile_details,
    )

    try:
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return False

        # Get the segment_id
        upload_history: ProspectUploadHistory = (
            ProspectUploadHistory.query.get(prospect_upload.prospect_upload_history_id)
            if prospect_upload.prospect_upload_history_id
            else None
        )
        if upload_history:
            segment_id = (
                upload_history.client_segment_id
                or get_base_segment_for_archetype(
                    archetype_id=upload_history.client_archetype_id
                )
            )
        else:
            segment_id = get_base_segment_for_archetype(
                prospect_upload.client_archetype_id
            )

        client_sdr: ClientSDR = ClientSDR.query.get(prospect_upload.client_sdr_id)

        # Mark the prospect upload row as UPLOAD_IN_PROGRESS.
        prospect_upload.upload_attempts += 1
        prospect_upload.status = ProspectUploadsStatus.UPLOAD_IN_PROGRESS
        db.session.add(prospect_upload)
        db.session.commit()

        email = prospect_upload.data.get("email", None)
        linkedin_url = prospect_upload.data.get("linkedin_url", None)
        is_lookalike_profile = prospect_upload.data.get("is_lookalike_profile", False)

        # If don't have a li_url but we have an email (and name, company?), search for the li_url
        if not linkedin_url and email:
            company = prospect_upload.data.get("company", "")

            full_name = prospect_upload.data.get("full_name", "")
            first_name = prospect_upload.data.get("first_name", "")
            last_name = prospect_upload.data.get("last_name", "")

            valid = full_name or (first_name and last_name)
            if not valid:
                raise Exception(
                    "Not a valid name found to find email: {}".format(email)
                )

            result = search_for_li(
                email,
                client_sdr.timezone,
                str(full_name or first_name + " " + last_name).strip(),
                company,
            )

            if result:
                linkedin_url = result
                # print("Found LinkedIn URL: {}".format(linkedin_url))
            else:
                raise Exception("No LinkedIn URL found for email: {}".format(email))

        # Get the LinkedIn URL profile id for iScraper.
        if "/in/" in linkedin_url:
            slug = get_linkedin_slug_from_url(linkedin_url)
        elif "/lead/" in linkedin_url:
            slug = get_navigator_slug_from_url(linkedin_url)

        # Get the iScraper payload. If the payload has errors, mark the prospect upload row as UPLOAD_FAILED and STOP.
        iscraper_payload = research_personal_profile_details(profile_id=slug)
        if not deep_get(iscraper_payload, "first_name"):
            error = get_iscraper_payload_error(iscraper_payload)
            prospect_upload.status = (
                ProspectUploadsStatus.DISQUALIFIED
                if error == "Profile data cannot be retrieved."
                else ProspectUploadsStatus.UPLOAD_FAILED
            )
            prospect_upload.error_type = ProspectUploadsErrorType.ISCRAPER_FAILED
            prospect_upload.error_message = error
            db.session.add(prospect_upload)
            db.session.commit()
            return False

        company_url = deep_get(iscraper_payload, "position_groups.0.company.url")
        if company_url and "linkedin.com/" in company_url:
            company_slug = company_url.split(".com/")[1].split("/")[1]
            company_info = research_corporate_profile_details(company_name=company_slug)
            new_company_url = deep_get(company_info, "details.urls.company_page")
            if new_company_url:
                company_url = new_company_url

        # Get Prospect fields - needs change in future
        company_name = deep_get(iscraper_payload, "position_groups.0.company.name")
        employee_count = (
            str(deep_get(iscraper_payload, "position_groups.0.company.employees.start"))
            + "-"
            + str(deep_get(iscraper_payload, "position_groups.0.company.employees.end"))
        )
        full_name = (
            deep_get(iscraper_payload, "first_name")
            + " "
            + deep_get(iscraper_payload, "last_name")
        )
        industry = deep_get(iscraper_payload, "industry")
        linkedin_url = "linkedin.com/in/{}".format(
            deep_get(iscraper_payload, "profile_id")
        )
        linkedin_bio = deep_get(iscraper_payload, "summary")
        title = deep_get(
            iscraper_payload, "position_groups.0.profile_positions.0.title"
        ) or deep_get(iscraper_payload, "sub_title")
        twitter_url = None

        # Health Check fields
        followers_count = (
            deep_get(iscraper_payload, "network_info.followers_count") or 0
        )

        education_1 = deep_get(iscraper_payload, "education.0.school.name")
        education_2 = deep_get(iscraper_payload, "education.1.school.name")

        prospect_location = "{}, {}, {}".format(
            deep_get(iscraper_payload, "location.city", default="") or "",
            deep_get(iscraper_payload, "location.state", default="") or "",
            deep_get(iscraper_payload, "location.country", default="") or "",
        )
        company_location = deep_get(
            iscraper_payload,
            "position_groups.0.profile_positions.0.location",
            default="",
        )

        # Add prospect
        new_prospect_id = add_prospect(
            client_id=prospect_upload.client_id,
            archetype_id=prospect_upload.client_archetype_id,
            client_sdr_id=prospect_upload.client_sdr_id,
            prospect_upload_id=prospect_upload.id,
            company=company_name,
            company_url=company_url,
            employee_count=employee_count,
            full_name=full_name,
            industry=industry,
            synchronous_research=True,
            linkedin_url=linkedin_url,
            linkedin_bio=linkedin_bio,
            title=title,
            twitter_url=twitter_url,
            email=email,
            linkedin_num_followers=followers_count,
            allow_duplicates=allow_duplicates,
            segment_id=segment_id,
            education_1=education_1,
            education_2=education_2,
            prospect_location=prospect_location,
            company_location=company_location,
            is_lookalike_profile=is_lookalike_profile,
        )
        if new_prospect_id is not None:
            create_iscraper_payload_cache(
                linkedin_url=linkedin_url,
                payload=iscraper_payload,
                payload_type=IScraperPayloadType.PERSONAL,
            )
            prospect_upload.status = ProspectUploadsStatus.UPLOAD_COMPLETE
            db.session.add(prospect_upload)
            db.session.commit()
            run_and_assign_health_score.apply_async(
                args=[None, new_prospect_id],
                queue="prospecting",
                routing_key="prospecting",
                priority=5,
            )
            generate_prospect_research.apply_async(
                args=[new_prospect_id, False, False],
                queue="prospecting",
                routing_key="prospecting",
                priority=5,
            )

            custom_data = prospect_upload.data.get("custom_data", {})
            # TODO: Change this to pull label from the data
            research_point_type_id = create_custom_research_point_type(
                prospect_id=new_prospect_id, label="CUSTOM", data=custom_data
            )

            if mark_prospect_as_is_champion:
                mark_prospects_as_champion(
                    client_id=prospect_upload.client_id,
                    prospect_ids=[new_prospect_id],
                    is_champion=mark_prospect_as_is_champion,
                )

            return True, new_prospect_id
        else:
            prospect_upload.status = ProspectUploadsStatus.DISQUALIFIED
            prospect_upload.error_type = ProspectUploadsErrorType.DUPLICATE
            db.session.add(prospect_upload)
            db.session.commit()
            return False, prospect_upload_id
    except Exception as e:
        db.session.rollback()
        prospect_upload: ProspectUploads = ProspectUploads.query.get(prospect_upload_id)
        if not prospect_upload:
            return False, -1

        # Mark as Failed
        prospect_upload.status = ProspectUploadsStatus.UPLOAD_FAILED
        db.session.add(prospect_upload)
        db.session.commit()

        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def run_and_assign_health_score(
    self,
    archetype_id: Optional[int] = None,
    prospect_id: Optional[int] = None,
    live: Optional[bool] = False,
):
    """Celery task for running and assigning health scores to prospects.

    Only runs on prospects that have not been assigned a health score.

    Args:
        archetype_id (int): The archetype id to run the health score on.
        prospect_id (int): The prospect id to run the health score on.
        live (bool): Whether or not to run the task in live mode.

    Raises:
        self.retry: If the task fails, it will retry, up to the max_retries limit.
    """
    # Get the prospects for the archetype
    try:
        # Add a short_circuit which will use prospect_id
        if prospect_id is not None:
            prospect: Prospect = Prospect.query.filter_by(
                id=prospect_id,
                health_check_score=None,
            ).first()
            client_sdr_id = prospect.client_sdr_id
            archetype_id = prospect.archetype_id

            if not prospect:
                return

            if (
                prospect.li_num_followers is None
            ):  # This should only happen on existent records, iScraper won't give None here.
                return

            health_score = 0

            if prospect.linkedin_bio is not None and len(prospect.linkedin_bio) > 0:
                health_score += 25

            # Calculate score based off of Sigmoid Function (using follower count)
            sig_score = calculate_health_check_follower_sigmoid(
                prospect.li_num_followers or 0
            )
            health_score += sig_score

            prospect.health_check_score = health_score
            db.session.add(prospect)
            db.session.commit()
            prospect_id = prospect.id

            if not live:
                # icp_classify.apply_async(
                #     args=[prospect.id, client_sdr_id, archetype_id],
                #     queue="ml_prospect_classification",
                #     routing_key="ml_prospect_classification",
                #     priority=3,
                # )
                apply_icp_scoring_ruleset_filters_task(
                    client_archetype_id=archetype_id,
                    prospect_ids=[prospect_id],
                )
            else:
                apply_icp_scoring_ruleset_filters_task(
                    client_archetype_id=archetype_id,
                    prospect_ids=[prospect_id],
                )
                # icp_classify(prospect_id=prospect.id, client_sdr_id=client_sdr_id, archetype_id=archetype_id)
            return

        # Regular, archetype-wide health score
        prospects: list[Prospect] = Prospect.query.filter_by(
            archetype_id=archetype_id,
            health_check_score=None,
        ).all()

        update_prospects: list[dict] = []
        for p in prospects:
            if (
                p.li_num_followers is None
            ):  # This should only happen on existent records, iScraper won't give None here.
                continue

            health_score = 0

            if p.linkedin_bio is not None and len(p.linkedin_bio) > 0:
                health_score += 25

            # Calculate score based off of Sigmoid Function (using follower count)
            sig_score = calculate_health_check_follower_sigmoid(p.li_num_followers or 0)
            health_score += sig_score

            update_prospects.append({"p_id": p.id, "health_score": health_score})

        # UPDATE prospect WHERE id = :id SET health_check_score = :health_score

        if len(update_prospects) > 0:
            stmt = (
                update(Prospect)
                .where(Prospect.id == bindparam("p_id"))
                .values(health_check_score=bindparam("health_score"))
            )
            db.session.execute(stmt, update_prospects)
            db.session.commit()

        return (
            True,
            "Successfully calculated health check scores for archetype: {}".format(
                archetype_id
            ),
        )
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
    k = 0.015  # Sigmoid function constant
    midpoint = 300  # Sigmoid function midpoint
    upper_bound = 75  # Sigmoid function upper bound
    raw_sig_score = upper_bound / (1 + math.exp(-k * (num_followers - midpoint)))
    y_intercept_adjuster = upper_bound / (1 + math.exp(k * midpoint))
    sig_score = raw_sig_score - y_intercept_adjuster

    return sig_score


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def refresh_bio_followers_for_prospect(self, prospect_id: int):
    from src.research.linkedin.services import research_personal_profile_details

    try:
        p = Prospect.query.get(prospect_id)
        print(p)
        li_slug = get_linkedin_slug_from_url(p.linkedin_url)
        scraper_payload = research_personal_profile_details(li_slug)
        if not deep_get(scraper_payload, "first_name"):
            return ("scraper_error", scraper_payload)

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


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def run_and_assign_intent_score(self, prospect_id: int):
    """Runs and assigns a Prospect.email_intent_score and Prospect.li_intent_score based on either their LI or their Email

    Args:
        prospect_id (int): The prospect id to run the intent score on.
    """
    try:
        # Get Prospect
        p: Prospect = Prospect.query.get(prospect_id)
        if p is None:
            return False

        # Get ICP fit score
        icp_fit_score = p.icp_fit_score or -1
        weighted_fit_score = calculate_weighted_fit_score(icp_fit_score)

        # Get Intent Score for LI
        if p.health_check_score is not None:
            li_intent_score = p.health_check_score * 0.5 + weighted_fit_score
            p.li_intent_score = li_intent_score

        # Get Intent Score for Email
        if p.email_score is not None:
            email_intent_score = p.email_score * 0.5 + weighted_fit_score
            p.email_intent_score = email_intent_score

        db.session.add(p)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def calculate_weighted_fit_score(icp_fit_score: int) -> float:
    """Calculates the weighted fit score for a prospect.

    icp_fit_score ranges between 0 and 4, we apply a simple scalar to get a weighted fit score between 0 and 50.

    Args:
        icp_fit_score (int): The ICP fit score for a prospect.

    Returns:
        int: The weighted fit score for a prospect.
    """
    return (icp_fit_score / 4) * 50


def get_most_recent_apollo_query(client_sdr_id: int):
    data = db.session.execute(
        f"""
            select data
            from saved_apollo_query
            where saved_apollo_query.client_sdr_id = {client_sdr_id}
              and saved_apollo_query.is_prefilter
            order by saved_apollo_query.created_at desc
            limit 1;
          """
    ).fetchall()
    return data[0][0] if data and data[0] else None


def upload_prospects_from_apollo_query(
    client_sdr_id: int,
    apollo_filters: dict,
    page: int = 1,
    archetype_id: int = None,
    segment_id: int = None,
):
    from src.contacts.services import apollo_get_contacts_for_page

    response, data, saved_query_id = apollo_get_contacts_for_page(
        client_sdr_id=client_sdr_id,
        page=page,
        person_titles=apollo_filters.get("person_titles"),
        person_not_titles=apollo_filters.get("person_not_titles"),
        q_person_title=apollo_filters.get("q_person_title"),
        q_person_name=apollo_filters.get("q_person_name"),
        organization_industry_tag_ids=apollo_filters.get(
            "organization_industry_tag_ids"
        ),
        organization_num_employees_ranges=apollo_filters.get(
            "organization_num_employees_ranges"
        ),
        person_locations=apollo_filters.get("person_locations"),
        organization_ids=apollo_filters.get("organization_ids"),
        revenue_range=apollo_filters.get("revenue_range"),
        organization_latest_funding_stage_cd=apollo_filters.get(
            "organization_latest_funding_stage_cd"
        ),
        currently_using_any_of_technology_uids=apollo_filters.get(
            "currently_using_any_of_technology_uids"
        ),
        event_categories=apollo_filters.get("event_categories"),
        published_at_date_range=apollo_filters.get("published_at_date_range"),
        person_seniorities=apollo_filters.get("person_seniorities"),
        q_organization_search_list_id=apollo_filters.get(
            "q_organization_search_list_id"
        ),
        organization_department_or_subdepartment_counts=apollo_filters.get(
            "organization_department_or_subdepartment_counts"
        ),
        is_prefilter=True,
    )

    total_pages = response.get("pagination").get("total_pages")
    people = response.get("people", [])

    if archetype_id is None:
        client_sdr_unassigned_archetype: ClientArchetype = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == client_sdr_id,
            ClientArchetype.is_unassigned_contact_archetype == True,
        ).first()
        if not client_sdr_unassigned_archetype:
            return None
        archetype_id = client_sdr_unassigned_archetype.id

    from src.prospecting.controllers import add_prospect_from_csv_payload

    add_prospect_from_csv_payload(
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        csv_payload=[
            {
                "linkedin_url": p.get("linkedin_url"),
                "first_name": p.get("first_name"),
                "last_name": p.get("last_name"),
            }
            for p in people
        ],
        allow_duplicates=False,
        source=ProspectUploadSource.CONTACT_DATABASE,
        segment_id=segment_id,
    )

    return [{"linkedin_url": p.get("linkedin_url")} for p in people], total_pages


@celery.task
def auto_run_apollo_upload_for_sdrs():
    # Auto scrape jobs
    sdrs: list[ClientSDR] = ClientSDR.query.all()
    for sdr in sdrs:
        if sdr.meta_data:
            if sdr.meta_data.get("apollo_auto_scrape") is True:
                pass
            else:
                continue
        else:
            continue

        # Turn off auto scrape
        if not sdr.meta_data:
            sdr.meta_data = {}
        sdr.meta_data["apollo_auto_scrape"] = False
        flag_modified(sdr, "meta_data")
        db.session.add(sdr)
        db.session.commit()

        upsert_and_run_apollo_upload_for_sdr(
            client_sdr_id=sdr.id, name="Auto Scrape", archetype_id=None, segment_id=None
        )

    # Run active jobs
    from src.automation.models import ApolloScraperJob

    jobs: list[ApolloScraperJob] = ApolloScraperJob.query.filter_by(active=True).all()
    for job in jobs:
        run_apollo_scraper_job(job_id=job.id)


@celery.task
def upsert_and_run_apollo_upload_for_sdr(
    client_sdr_id: int, name: str, archetype_id: int = None, segment_id: int = None
):
    from src.automation.models import ApolloScraperJob

    job: ApolloScraperJob = ApolloScraperJob.query.filter_by(
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        segment_id=segment_id,
    ).first()

    if not job:
        job_id = create_apollo_scraper_job(
            client_sdr_id=client_sdr_id,
            name=name,
            filters=get_most_recent_apollo_query(client_sdr_id),
            archetype_id=archetype_id,
            segment_id=segment_id,
            page_num=1,
            page_size=100,
            active=False,
        )
    else:
        job_id = job.id

    # Run the job
    run_apollo_scraper_job(job_id)


def get_apollo_scraper_jobs(client_sdr_id: int):
    from src.automation.models import ApolloScraperJob

    jobs: list[ApolloScraperJob] = ApolloScraperJob.query.filter_by(
        client_sdr_id=client_sdr_id
    ).all()

    return [job.to_dict() for job in jobs]


def create_apollo_scraper_job(
    client_sdr_id: int,
    name: str,
    filters: dict,
    archetype_id: Optional[int] = None,
    segment_id: Optional[int] = None,
    page_num: int = 1,
    page_size: int = 100,
    active: bool = False,
):
    from src.automation.models import ApolloScraperJob

    job: ApolloScraperJob = ApolloScraperJob.query.filter_by(
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        segment_id=segment_id,
    ).first()

    if job:
        job.name = name
        job.active = active
        job.page_num = page_num
        job.page_size = page_size
        job.filters = filters
    else:
        job = ApolloScraperJob(
            client_sdr_id=client_sdr_id,
            name=name,
            archetype_id=archetype_id,
            segment_id=segment_id,
            page_num=page_num,
            page_size=page_size,
            active=active,
            filters=filters,
        )

    db.session.add(job)
    db.session.commit()

    return job.id


def update_apollo_scraper_job(
    job_id: int, name: str = None, active: bool = None, update_filters: bool = None
):
    from src.automation.models import ApolloScraperJob

    job: ApolloScraperJob = ApolloScraperJob.query.get(job_id)

    if not job:
        return None

    if name:
        job.name = name
    if active is not None:
        job.active = active
    if update_filters:
        job.filters = get_most_recent_apollo_query(job.client_sdr_id)

    db.session.add(job)
    db.session.commit()

    return job.to_dict()


@celery.task
def run_apollo_scraper_job(job_id: int):
    from src.automation.models import ApolloScraperJob, ProcessQueue, ProcessQueueStatus
    from sqlalchemy import Integer

    results: list[ProcessQueue] = (
        ProcessQueue.query.filter(ProcessQueue.type == "upload_from_apollo")
        .filter(ProcessQueue.meta_data["args"]["job_id"].astext.cast(Integer) == job_id)
        .filter(ProcessQueue.status != ProcessQueueStatus.FAILED)
        .all()
    )

    if len(results) > 0:
        return

    job: ApolloScraperJob = ApolloScraperJob.query.get(job_id)
    job.active = True
    db.session.add(job)
    db.session.commit()

    upload_from_apollo(job_id=job_id, max_pages=job.max_pages if job.max_pages else 1)


@celery.task
def upload_from_apollo(job_id: int, max_pages: int):
    from src.automation.models import ApolloScraperJob

    job: ApolloScraperJob = ApolloScraperJob.query.get(job_id)

    if not job.active or job.page_num > max_pages:
        job.active = False
        db.session.add(job)
        db.session.commit()
        return None

    person_urls, total_pages = upload_prospects_from_apollo_query(
        client_sdr_id=job.client_sdr_id,
        apollo_filters=job.filters,
        page=job.page_num,
        archetype_id=job.archetype_id,
        segment_id=job.segment_id,
    )

    from src.utils.datetime.dateutils import get_future_datetime
    import datetime

    # String of the first 2 and last 2 person urls
    person_urls_str = (
        "\n".join([p.get("linkedin_url") for p in person_urls[:2] if p])
        + "\n...\n"
        + "\n".join([p.get("linkedin_url") for p in person_urls[-2:] if p])
    )

    from src.utils.slack import send_slack_message, URL_MAP
    from src.automation.orchestrator import add_process_for_future

    sdr: ClientSDR = ClientSDR.query.get(job.client_sdr_id)

    send_slack_message(
        message=f"✅ <{job.name}> Imported contacts for `{sdr.name}`'s territory\nPage #{job.page_num} - {max_pages}\n{len(person_urls)} prospects imported. \n Example Profiles: \n {person_urls_str} \n {get_future_datetime(0, 0, 60, datetime.datetime.utcnow()).isoformat()} \n {datetime.datetime.utcnow().isoformat()} \n {get_future_datetime(0, 0, 60, datetime.datetime.now(datetime.timezone.utc)).isoformat()}",
        webhook_urls=[URL_MAP["ops-territory-scraper"]],
    )

    job.page_num += 1
    job.max_pages = total_pages
    db.session.add(job)
    db.session.commit()

    add_process_for_future(
        type="upload_from_apollo",
        args={
            "job_id": job_id,
            "max_pages": total_pages,
        },
        days=1,
    )

    return person_urls


# @celery.task
# def auto_upload_from_apollo(client_sdr_id: int, page: int = 1, max_pages: int = 5):
#     sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

#     if sdr.meta_data is None:
#         return None

#     if sdr.meta_data:
#         if sdr.meta_data.get("apollo_auto_scrape") is True or page != 1:
#             pass
#         else:
#             return None
#     else:
#         return None

#     # Turn off auto scrape
#     if not sdr.meta_data:
#         sdr.meta_data = {}
#     sdr.meta_data["apollo_auto_scrape"] = False
#     flag_modified(sdr, "meta_data")
#     db.session.add(sdr)
#     db.session.commit()

#     if page > max_pages:
#         return None

#     from src.utils.slack import send_slack_message, URL_MAP
#     from src.automation.orchestrator import add_process_for_future

#     apollo_filters = get_most_recent_apollo_query(client_sdr_id)
#     if not apollo_filters:
#         return None

#     person_urls = upload_prospects_from_apollo_query(
#         client_sdr_id=client_sdr_id, apollo_filters=apollo_filters, page=page
#     )

#     from src.utils.datetime.dateutils import get_future_datetime
#     import datetime

#     # String of the first 2 and last 2 person urls
#     person_urls_str = (
#         "\n".join([p.get("linkedin_url") for p in person_urls[:2]])
#         + "\n...\n"
#         + "\n".join([p.get("linkedin_url") for p in person_urls[-2:]])
#     )

#     send_slack_message(
#         message=f"✅ Auto imported contacts for `{sdr.name}`'s territory\nPage #{page} - {max_pages}\n{len(person_urls)} prospects imported. \n Example Profiles: \n {person_urls_str} \n {get_future_datetime(0, 0, 60, datetime.datetime.utcnow()).isoformat()} \n {datetime.datetime.utcnow().isoformat()} \n {get_future_datetime(0, 0, 60, datetime.datetime.now(datetime.timezone.utc)).isoformat()}",
#         webhook_urls=[URL_MAP["ops-territory-scraper"]],
#     )

#     add_process_for_future(
#         type="auto_upload_from_apollo",
#         args={
#             "client_sdr_id": client_sdr_id,
#             "page": page + 1,
#             "max_pages": max_pages,
#         },
#         minutes=60,
#     )

#     return person_urls
