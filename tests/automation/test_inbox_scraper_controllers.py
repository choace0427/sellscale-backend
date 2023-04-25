from app import db, app
import pytest
from decorators import use_app_context
import json
from src.automation.inbox_scraper import scrape_all_inboxes
from test_utils import test_app, basic_client, basic_client_sdr
import mock
from src.automation.models import PhantomBusterConfig


class FakePostResponse:
    text = json.dumps({"s3Folder": "123", "orgS3Folder": "456"})

    def json(self):
        return {"text": "{" + "}"}


@use_app_context
@mock.patch("src.automation.inbox_scraper.scrape_inbox.delay")
def test_scrape_all_inboxes(scrape_patch):
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id

    pb: PhantomBusterConfig = PhantomBusterConfig(
        client_id=client.id,
        client_sdr_id=sdr_id,
        pb_type="INBOX_SCRAPER",
        google_sheets_uuid="TEST_UUID",
        phantom_name="TEST_NAME",
        phantom_uuid="TEST_UUID",
    )
    db.session.add(pb)
    db.session.commit()

    scrape_all_inboxes()

    assert scrape_patch.call_count == 1


@use_app_context
@mock.patch("src.automation.inbox_scraper.scrape_inbox.delay")
def test_scrape_all_inboxes_fake_payload(scrape_inbox_patch):
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id

    pb: PhantomBusterConfig = PhantomBusterConfig(
        client_id=client.id,
        client_sdr_id=sdr_id,
        pb_type="INBOX_SCRAPER",
        google_sheets_uuid="TEST_UUID",
        phantom_name="TEST_NAME",
        phantom_uuid="TEST_UUID",
    )
    db.session.add(pb)
    db.session.commit()

    scrape_all_inboxes()

    assert scrape_inbox_patch.call_count == 1
