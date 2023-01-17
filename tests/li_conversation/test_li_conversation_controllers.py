from app import db
from app import app
import json
import pandas as pd
import re
import csv


def test_get_li_conversation():
    """Test get_li_conversation"""
    response = app.test_client().get("/li_conversation/")
    assert response.status_code == 200
    data = response.data
    assert "linkedin_url" in data.decode("utf-8")
