from app import db
from decorators import use_app_context
from test_utils import test_app
from model_import import EditorTypes, Editor, Client

from app import app
import json
import mock


@use_app_context
def test_get_li_conversation():
    """Test get_li_conversation"""
    client = Client(
        company="test_company",
        contact_name="test_contact_name",
        contact_email="test_contact_email",
    )
    db.session.add(client)
    db.session.commit()

    response = app.test_client().get(
        "/li_conversation/{client_id}".format(client_id=client.id)
    )
    assert response.status_code == 200
    data = response.data
    assert "linkedin_url" in data.decode("utf-8")
