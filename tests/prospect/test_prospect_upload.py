from app import db
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_prospect,
    basic_archetype,
    basic_prospect_uploads_raw_csv,
    basic_prospect_uploads,
)
from model_import import (
    Prospect,
    ProspectUploadsRawCSV,
    ProspectUploads,
    ProspectUploadsStatus,
    ProspectUploadsErrorType,
)
from src.prospecting.upload.services import (
    create_raw_csv_entry_from_json_payload,
    populate_prospect_uploads_from_json_payload,
    collect_and_run_celery_jobs_for_upload,
    create_prospect_from_prospect_upload_row,
    create_prospect_from_linkedin_link,
    run_and_assign_health_score,
    calculate_health_check_follower_sigmoid
)

import mock
import pytest
import random


VALID_ISCRAPER_PAYLOAD = {
    "first_name": "John",
    "last_name": "Doe",
    "industry": "Software",
    "summary": "I am a software engineer",
    "sub_title": "Software Engineer",
    "position_groups": [
        {
            "company": {
                "name": "Google",
                "url": "https://www.google.com",
                "employees": {"start": 2019, "end": 2022},
            },
        }
    ],
}

ERROR_ISCRAPER_PAYLOAD = {"message": "Some iScraper message"}
BAD_ISCRAPER_PAYLOAD = {"detail": "Profile data cannot be retrieved."}


@use_app_context
def test_create_raw_csv_entry_from_json_payload():
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)

    payload = [
        {
            "test1": "test",
        },
        {
            "test2": "test",
        },
    ]
    raw_csv_entry_id = create_raw_csv_entry_from_json_payload(
        c.id, a.id, sdr.id, payload
    )
    assert ProspectUploadsRawCSV.query.count() == 1
    raw_csv_entry: ProspectUploadsRawCSV = ProspectUploadsRawCSV.query.filter_by(
        id=raw_csv_entry_id
    ).first()
    assert raw_csv_entry.csv_data == payload

    # Check that we can't create a duplicate entry.
    raw_csv_entry_id = create_raw_csv_entry_from_json_payload(
        c.id, a.id, sdr.id, payload
    )
    assert ProspectUploadsRawCSV.query.count() == 1
    assert raw_csv_entry_id == -1


@use_app_context
def test_populate_prospect_uploads_from_json_payload():
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(
        client=c, client_archetype=a, client_sdr=sdr
    )

    payload = [
        {
            "test1": "test",
        },
        {
            "test2": "test",
        },
    ]
    populated = populate_prospect_uploads_from_json_payload(
        c.id, a.id, sdr.id, raw_csv_entry.id, payload
    )
    assert populated
    assert ProspectUploads.query.count() == 2
    prospect_uploads: list[ProspectUploads] = ProspectUploads.query.filter_by(
        prospect_uploads_raw_csv_id=raw_csv_entry.id
    ).all()
    assert prospect_uploads[0].csv_row_data == payload[0]
    assert prospect_uploads[1].csv_row_data == payload[1]

    # Check that duplicate entries are automatically disqualified
    populated = populate_prospect_uploads_from_json_payload(
        c.id, a.id, sdr.id, raw_csv_entry.id, payload
    )
    assert populated
    assert ProspectUploads.query.count() == 4
    prospect_uploads: list[ProspectUploads] = ProspectUploads.query.filter_by(
        prospect_uploads_raw_csv_id=raw_csv_entry.id
    ).all()
    assert prospect_uploads[2].csv_row_data == payload[0]
    assert prospect_uploads[3].csv_row_data == payload[1]
    assert prospect_uploads[2].status == ProspectUploadsStatus.DISQUALIFIED
    assert prospect_uploads[3].status == ProspectUploadsStatus.DISQUALIFIED
    assert prospect_uploads[2].error_type == ProspectUploadsErrorType.DUPLICATE
    assert prospect_uploads[3].error_type == ProspectUploadsErrorType.DUPLICATE


@use_app_context
@mock.patch(
    "src.prospecting.upload.services.create_prospect_from_prospect_upload_row.apply_async"
)
def test_collect_and_run_celery_jobs_for_upload(celery_create_prospect_mock):
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(
        client=c, client_archetype=a, client_sdr=sdr
    )
    pu = basic_prospect_uploads(
        client=c,
        client_archetype=a,
        client_sdr=sdr,
        prospect_uploads_raw_csv=raw_csv_entry,
    )

    ran = collect_and_run_celery_jobs_for_upload(c.id, a.id, sdr.id)
    assert ran
    assert pu.status == ProspectUploadsStatus.UPLOAD_QUEUED
    assert celery_create_prospect_mock.call_count == 1
    assert celery_create_prospect_mock.called_with(pu.id)


@use_app_context
@mock.patch(
    "src.prospecting.upload.services.create_prospect_from_linkedin_link.apply_async"
)
def test_create_prospect_from_prospect_upload_row(celery_create_prospect_mock):
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(
        client=c, client_archetype=a, client_sdr=sdr
    )
    pu = basic_prospect_uploads(
        client=c,
        client_archetype=a,
        client_sdr=sdr,
        prospect_uploads_raw_csv=raw_csv_entry,
    )

    # Check that we call a celery worker to create a prospect from a row with a linkedin link
    create_prospect_from_prospect_upload_row(pu.id)
    assert celery_create_prospect_mock.call_count == 1
    assert celery_create_prospect_mock.called_with(
        prospect_upload_id=pu.client_archetype_id,
    )

    # Check that we can't create a prospect from a row without a valid prospect_upload_id
    create_prospect_from_prospect_upload_row(-1)
    assert celery_create_prospect_mock.call_count == 1


@use_app_context
@mock.patch(
    "src.prospecting.upload.services.research_personal_profile_details",
    return_value=ERROR_ISCRAPER_PAYLOAD,
)
def test_create_prospect_from_linkedin_link_iscraper_error(
    iscraper_research_personal_profile_details_mock,
):
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(
        client=c, client_archetype=a, client_sdr=sdr
    )
    pu = basic_prospect_uploads(
        client=c,
        client_archetype=a,
        client_sdr=sdr,
        prospect_uploads_raw_csv=raw_csv_entry,
    )
    pu_id = pu.id

    # Check that the ERROR iScraper payload will result in a failed prospect upload
    success = create_prospect_from_linkedin_link(pu_id)
    pu: ProspectUploads = ProspectUploads.query.get(pu_id)
    assert not success
    assert pu.status == ProspectUploadsStatus.UPLOAD_FAILED
    assert pu.error_type == ProspectUploadsErrorType.ISCRAPER_FAILED
    assert pu.iscraper_error_message == "Some iScraper message"

    with mock.patch(
        "src.prospecting.upload.services.research_personal_profile_details",
        return_value=BAD_ISCRAPER_PAYLOAD,
    ):
        # Check that the prospect should be disqualified
        success = create_prospect_from_linkedin_link(pu_id)
        pu: ProspectUploads = ProspectUploads.query.get(pu_id)
        assert not success
        assert pu.status == ProspectUploadsStatus.DISQUALIFIED
        assert pu.error_type == ProspectUploadsErrorType.ISCRAPER_FAILED
        assert pu.iscraper_error_message == "Profile data cannot be retrieved."


@use_app_context
@mock.patch(
    "src.prospecting.upload.services.research_personal_profile_details",
    return_value=VALID_ISCRAPER_PAYLOAD,
)
def test_create_prospect_from_linkedin_link_successful(
    iscraper_research_personal_profile_details_mock,
):
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(
        client=c, client_archetype=a, client_sdr=sdr
    )
    pu = basic_prospect_uploads(
        client=c,
        client_archetype=a,
        client_sdr=sdr,
        prospect_uploads_raw_csv=raw_csv_entry,
    )
    pu_id = pu.id

    # Check that we can't create a prospect from a row without a valid prospect upload
    assert create_prospect_from_linkedin_link(-1) == False

    # Check that we can create a prospect
    success = create_prospect_from_linkedin_link(pu_id)
    pu = ProspectUploads.query.get(pu_id)
    assert success
    assert iscraper_research_personal_profile_details_mock.call_count == 1
    assert pu.status == ProspectUploadsStatus.UPLOAD_COMPLETE
    assert Prospect.query.count() == 1


@use_app_context
@mock.patch(
    "src.prospecting.upload.services.research_personal_profile_details",
    return_value=VALID_ISCRAPER_PAYLOAD,
)
def test_create_prospect_from_linkedin_link_successful(
    iscraper_research_personal_profile_details_mock,
):
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(
        client=c, client_archetype=a, client_sdr=sdr
    )
    pu = basic_prospect_uploads(
        client=c,
        client_archetype=a,
        client_sdr=sdr,
        prospect_uploads_raw_csv=raw_csv_entry,
    )
    pu_id = pu.id

    # Check that we can't create a prospect from a row without a valid prospect upload
    assert create_prospect_from_linkedin_link(-1) == False

    # Check that we can create a prospect
    success = create_prospect_from_linkedin_link(pu_id)
    pu = ProspectUploads.query.get(pu_id)
    assert success
    assert iscraper_research_personal_profile_details_mock.call_count == 1
    assert pu.status == ProspectUploadsStatus.UPLOAD_COMPLETE
    assert Prospect.query.count() == 1


@use_app_context
@mock.patch(
    "src.prospecting.upload.services.research_personal_profile_details",
    side_effect=Exception("Some exception"),
)
def test_create_prospect_from_linkedin_link_failure(
    iscraper_research_personal_profile_details_mock,
):
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(
        client=c, client_archetype=a, client_sdr=sdr
    )
    pu = basic_prospect_uploads(
        client=c,
        client_archetype=a,
        client_sdr=sdr,
        prospect_uploads_raw_csv=raw_csv_entry,
    )
    pu_id = pu.id

    with pytest.raises(Exception):
        # Check that we can create a prospect
        success = create_prospect_from_linkedin_link(pu_id)
        pu: ProspectUploads = ProspectUploads.query.get(pu_id)
        assert not success
        assert pu.status == ProspectUploadsStatus.UPLOAD_FAILED
        assert pu.upload_attempts == 1


@use_app_context
def test_run_and_assign_health_score():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_2 = basic_prospect(client, archetype, sdr)
    prospect_3 = basic_prospect(client, archetype, sdr)
    prospect_4 = basic_prospect(client, archetype, sdr)
    prospect.linkedin_bio = ""                  # Should get 0 points
    prospect.li_num_followers = 0
    prospect_2.linkedin_bio = "Some bio"        # Should get 25 points
    prospect_2.li_num_followers = 0
    prospect_3.linkedin_bio = "Some bio"        # Should get around 25 + 37.5 points
    prospect_3.li_num_followers = 300
    prospect_4.linkedin_bio = "Some bio"        # Should get some points > 25 + 37.5 but < 100
    prospect_4.li_num_followers = 1000
    prospect_id = prospect.id
    prospect_2_id = prospect_2.id
    prospect_3_id = prospect_3.id
    prospect_4_id = prospect_4.id
    db.session.add(prospect)
    db.session.add(prospect_2)
    db.session.add(prospect_3)
    db.session.add(prospect_4)
    db.session.commit()

    response = run_and_assign_health_score(archetype_id)
    assert response[0] == True

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_2: Prospect = Prospect.query.get(prospect_2_id)
    prospect_3: Prospect = Prospect.query.get(prospect_3_id)
    prospect_4: Prospect = Prospect.query.get(prospect_4_id)
    assert prospect.health_check_score == 0
    assert prospect_2.health_check_score == 25
    assert prospect_3.health_check_score > 60 and prospect_3.health_check_score < 63
    assert prospect_4.health_check_score > 62.5 and prospect_4.health_check_score < 100


@use_app_context
def test_calculate_health_check_follower_sigmoid():
    for i in range(0, 100):
        random_follower_count = random.randint(0, 1000)
        random_high_count = random.randint(1000, 10000)

        score = calculate_health_check_follower_sigmoid(random_follower_count)
        assert score >= 0 and score <= 75

        high_score = calculate_health_check_follower_sigmoid(random_high_count)
        assert high_score >= 37.5 and high_score <= 75      # We know this to be true since our midpoint is set to 300
