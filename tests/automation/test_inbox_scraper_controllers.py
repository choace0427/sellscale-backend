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
@mock.patch(
    "src.automation.services.requests.request",
    return_value=FakePostResponse(),
)
def test_scrape_all_inboxes(request_patch):
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


@use_app_context
@mock.patch(
    "src.automation.services.requests.request",
    return_value=FakePostResponse(),
)
@mock.patch(
    "src.automation.inbox_scraper.get_phantom_buster_payload",
    return_value=[
        {
            "firstnameFrom": "Zaheer",
            "isLastMessageFromMe": True,
            "lastMessageDate": "2022-10-20T06:01:08.960Z",
            "lastMessageFromUrl": "https://www.linkedin.com/in/zmohiuddin/",
            "lastnameFrom": "Mohiuddin",
            "linkedInUrls": ["https://www.linkedin.com/in/doug-ayers-7b8b10b/"],
            "message": "looking forward to it!",
            "occupationFrom": "Co-Founder at Levels.fyi | Get Paid, Not Played",
            "readStatus": True,
            "threadUrl": "https://www.linkedin.com/messaging/thread/2-MDllMWY4YzEtZGFjNy00NWU1LWFhYWYtZWVlZTczZmFjNWJkXzAxMg==",
            "timestamp": "2022-10-20T06:06:54.106Z",
        }
    ],
)
def test_scrape_all_inboxes_fake_payload(
    get_phantom_buster_payload_patch,
    request_patch,
):
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
