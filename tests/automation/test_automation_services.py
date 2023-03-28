import json
import mock
from app import db, app
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_phantom_buster_configs,
    basic_prospect,
    basic_archetype,
    basic_generated_message,
    basic_generated_message_cta,
    basic_gnlp_model
)
from src.automation.services import *

@use_app_context
@mock.patch("src.automation.models.PhantomBusterAgent.get_arguments", return_value={"sessionCookie": "some_cookie"})
def test_update_phantom_buster_li_at(pbagent_get_arguments_mock):
    client = basic_client()
    sdr = basic_client_sdr(client)
    inbox_phantom, outbound_phantom = basic_phantom_buster_configs(client, sdr)

    assert sdr.li_at_token == None

    update_phantom_buster_li_at(sdr.id, "TEST_LI_AT_TOKEN")
    assert sdr.li_at_token == "TEST_LI_AT_TOKEN"


@use_app_context
def test_create_pb_linkedin_invite_csv():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    gnlp = basic_gnlp_model(archetype)
    cta = basic_generated_message_cta(archetype)
    generated_message = basic_generated_message(prospect, gnlp, cta)
    generated_message.message_status = "QUEUED_FOR_OUTREACH"
    prospect.approved_outreach_message_id=generated_message.id
    prospect.linkedin_url = "https://www.linkedin.com/in/davidmwei"

    data = create_pb_linkedin_invite_csv(sdr.id)
    assert data == [
        {
            "Linkedin": "https://www.linkedin.com/in/davidmwei",
            "Message": "this is a test",
        }
    ]
