from app import db
from app import app
import json
import pandas as pd
import re
import csv
from test_utils import basic_client, basic_archetype, basic_prospect
from datetime import datetime, timedelta
from decorators import use_app_context


@use_app_context
def test_get_li_conversation():
    """Test get_li_conversation"""
    client = basic_client()
    archetype = basic_archetype(client=client)
    prospect = basic_prospect(client=client, archetype=archetype)

    prospect.li_last_message_timestamp = datetime.now() - timedelta(days=1)

    response = app.test_client().get("/li_conversation/")
    assert response.status_code == 200
    data = response.data
    assert "linkedin_url" in data.decode("utf-8")
