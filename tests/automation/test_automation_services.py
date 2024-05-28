import json
import mock
from app import db, app
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_outbound_campaign,
    basic_phantom_buster_configs,
    basic_prospect,
    basic_archetype,
    basic_generated_message,
    basic_generated_message_cta,
)
from src.automation.services import *


class FakePostResponse:
    def __init__(self, return_payload={"id": "TEST_ID"}):
        self.payload = return_payload

    def json(self):
        return self.payload


@use_app_context
@mock.patch(
    "src.automation.models.PhantomBusterAgent.get_arguments",
    return_value={"sessionCookie": "some_cookie"},
)
@mock.patch("src.automation.services.requests.request", return_value=FakePostResponse())
def test_update_phantom_buster_li_at(request_mock, pbagent_get_arguments_mock):
    client = basic_client()
    sdr = basic_client_sdr(client)
    inbox_phantom, outbound_phantom = basic_phantom_buster_configs(client, sdr)

    assert sdr.li_at_token == None

    update_phantom_buster_li_at(sdr.id, "TEST_LI_AT_TOKEN")
    assert sdr.li_at_token == "TEST_LI_AT_TOKEN"


@use_app_context
def test_create_pb_linkedin_invite_csv():
    from model_import import GeneratedMessage, Prospect

    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    prospect.status = "QUEUED_FOR_OUTREACH"
    prospect_id = prospect.id
    cta = basic_generated_message_cta(archetype)
    campaign = basic_outbound_campaign([prospect_id], "LINKEDIN", archetype, sdr)
    generated_message = basic_generated_message(prospect, cta, campaign)
    generated_message_id = generated_message.id
    generated_message.message_status = "QUEUED_FOR_OUTREACH"
    generated_message.priority_rating = 1
    generated_message_2 = basic_generated_message(prospect, cta, campaign)
    generated_message_2_id = generated_message_2.id
    generated_message_2.completion = "This is a higher priority message"
    generated_message_2.message_status = "QUEUED_FOR_OUTREACH"
    generated_message_2.priority_rating = 10
    generated_message_3 = basic_generated_message(prospect, cta, campaign)
    generated_message_3_id = generated_message_3.id
    generated_message_3.completion = "This is low priority, should not appear"
    generated_message_3.message_status = "QUEUED_FOR_OUTREACH"
    generated_message_3.priority_rating = 0
    prospect.approved_outreach_message_id = generated_message.id
    prospect.linkedin_url = "https://www.linkedin.com/in/davidmwei"

    data = create_pb_linkedin_invite_csv(sdr.id)
    assert data == [
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "This is a higher priority message",
        },
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "this is a test",
        },
    ]
    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.pb_csv_count == 1

    data = create_pb_linkedin_invite_csv(sdr.id)
    assert data == [
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "This is a higher priority message",
        },
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "this is a test",
        },
    ]
    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.pb_csv_count == 2

    data = create_pb_linkedin_invite_csv(sdr.id)
    assert data == [
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "This is a higher priority message",
        },
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "this is a test",
        },
    ]
    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.pb_csv_count == 3
    p: Prospect = Prospect.query.get(prospect_id)
    assert p.status.value == "SEND_OUTREACH_FAILED"

    data = create_pb_linkedin_invite_csv(sdr_id)
    assert data == [
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "This is low priority, should not appear",
        }
    ]


EXAMPLE_PB_WEBHOOK_RESPONSE_GOOD = {
    "resultObject": '[{"0" : "https://www.linkedin.com/in/davidmwei"}]',
    "exitCode": 0,
}


EXAMPLE_PB_WEBHOOK_RESPONSE_BAD = {
    "resultObject": '[{"0" : "https://www.linkedin.com/in/davidmwei", "error" : "Email needed to add this person"}]',
    "exitCode": 0,
}


@use_app_context
def test_update_pb_linkedin_send_status():
    from model_import import GeneratedMessage, Prospect

    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    p_id = prospect.id
    cta = basic_generated_message_cta(archetype)
    generated_message = basic_generated_message(prospect, cta)
    gm_id = generated_message.id
    generated_message.message_status = "QUEUED_FOR_OUTREACH"
    prospect.approved_outreach_message_id = generated_message.id
    prospect.linkedin_url = "https://www.linkedin.com/in/davidmwei"

    response = update_pb_linkedin_send_status(sdr.id, EXAMPLE_PB_WEBHOOK_RESPONSE_BAD)
    assert response == True
    generated_message = GeneratedMessage.query.get(gm_id)
    assert generated_message.message_status.value == "FAILED_TO_SEND"
    assert generated_message.failed_outreach_error == "Email needed to add this person"

    response = update_pb_linkedin_send_status(sdr.id, EXAMPLE_PB_WEBHOOK_RESPONSE_GOOD)
    assert response == True
    generated_message = GeneratedMessage.query.get(gm_id)
    assert generated_message.message_status.value == "SENT"
    assert generated_message.failed_outreach_error == None
    prospect = Prospect.query.get(p_id)
    assert prospect.status.value == "SENT_OUTREACH"
