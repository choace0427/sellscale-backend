import json
import mock
from app import db, app
from decorators import use_app_context
from test_utils import test_app, basic_client, basic_client_sdr, basic_phantom_buster_configs
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
