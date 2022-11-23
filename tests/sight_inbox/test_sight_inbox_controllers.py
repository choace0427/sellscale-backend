from app import db, app
from test_utils import test_app
from model_import import Echo
import pytest
from config import TestingConfig
from decorators import use_app_context
from test_utils import basic_client, basic_client_sdr
import json


@use_app_context
def test_get_empty_client_sdr_inbox():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_sdr_id = client_sdr.id

    response = app.test_client().get("/sight_inbox/{}".format(client_sdr_id))
    assert response.status_code == 200
    assert json.loads(response.data.decode("utf-8")) == []
