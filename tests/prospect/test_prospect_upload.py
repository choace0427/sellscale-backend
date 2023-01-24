from app import db
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect_uploads_raw_csv
)
from model_import import (
    ProspectUploadsRawCSV,
    ProspectUploads,
    ProspectUploadsStatus,
    ProspectUploadsErrorType
)
from src.prospecting.upload.services import (
    create_raw_csv_entry_from_json_payload,
    populate_prospect_uploads_from_json_payload
)

import mock
import json


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
        }
    ]
    raw_csv_entry_id = create_raw_csv_entry_from_json_payload(c.id, a.id, sdr.id, payload)
    assert ProspectUploadsRawCSV.query.count() == 1
    raw_csv_entry: ProspectUploadsRawCSV = ProspectUploadsRawCSV.query.filter_by(id=raw_csv_entry_id).first()
    assert raw_csv_entry.csv_data == payload

    # Check that we can't create a duplicate entry.
    raw_csv_entry_id = create_raw_csv_entry_from_json_payload(c.id, a.id, sdr.id, payload)
    assert ProspectUploadsRawCSV.query.count() == 1
    assert raw_csv_entry_id == -1


@use_app_context
def test_populate_prospect_uploads_from_json_payload():
    c = basic_client()
    a = basic_archetype(c)
    sdr = basic_client_sdr(c)
    raw_csv_entry = basic_prospect_uploads_raw_csv(client=c, client_archetype=a, client_sdr=sdr)

    payload = [
        {
            "test1": "test",
        },
        {
            "test2": "test",
        }
    ]
    populated = populate_prospect_uploads_from_json_payload(c.id, a.id, sdr.id, raw_csv_entry.id, payload)
    assert populated
    assert ProspectUploads.query.count() == 2
    prospect_uploads: list[ProspectUploads] = ProspectUploads.query.filter_by(prospect_uploads_raw_csv_id=raw_csv_entry.id).all()
    assert prospect_uploads[0].csv_row_data == payload[0]
    assert prospect_uploads[1].csv_row_data == payload[1]

    # Check that duplicate entries are automatically disqualified
    populated = populate_prospect_uploads_from_json_payload(c.id, a.id, sdr.id, raw_csv_entry.id, payload)
    assert populated
    assert ProspectUploads.query.count() == 4
    prospect_uploads: list[ProspectUploads] = ProspectUploads.query.filter_by(prospect_uploads_raw_csv_id=raw_csv_entry.id).all()
    assert prospect_uploads[2].csv_row_data == payload[0]
    assert prospect_uploads[3].csv_row_data == payload[1]
    assert prospect_uploads[2].status == ProspectUploadsStatus.DISQUALIFIED
    assert prospect_uploads[3].status == ProspectUploadsStatus.DISQUALIFIED
    assert prospect_uploads[2].error_type == ProspectUploadsErrorType.DUPLICATE
    assert prospect_uploads[3].error_type == ProspectUploadsErrorType.DUPLICATE




