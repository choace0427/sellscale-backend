from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr
)
from app import app
import mock

from src.research.linkedin.extractors.education import get_common_education


@use_app_context
def test_get_common_education():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr.questionnaire = {
        "education": [{
            "name": "University of California, Berkeley",
            "year_started": "2016",
            "year_ended": "2020",
            "degree": "Bachelor of Science",
        }]
    }

    # Prospect has no education
    no_education_payload = {
        "personal": {
            "first_name": "John",
            "last_name": "Doe",
            "education": [

            ]
        }
    }
    response = get_common_education(no_education_payload, client_sdr.id).get("response")
    assert response == ""

    # Prospect has education, but no common education
    no_common_education_payload = {
        "personal": {
            "first_name": "John",
            "last_name": "Doe",
            "education": [
                {
                    "school": {
                        "name": "University of California, Los Angeles"
                    },
                    "date": {
                        "start": "2015",
                        "end": "2019"
                    }
                }
            ]
        }
    }
    response = get_common_education(no_common_education_payload, client_sdr.id).get("response")
    assert response == ""

    # Prospect has education, and common education
    common_education_payload = {
        "personal": {
            "first_name": "John",
            "last_name": "Doe",
            "education": [
                {
                    "school": {
                        "name": "University of California, Berkeley"
                    },
                    "date": {
                        "start": "2015",
                        "end": "2019"
                    }
                }
            ]
        }
    }
    response = get_common_education(common_education_payload, client_sdr.id).get("response")
    assert response == "John Doe attended University of California, Berkeley from 2015 to 2019. I attended University of California, Berkeley from 2016 to 2020."


    # Prospect has education, and common education, but no date
    common_education_no_date_payload = {
        "personal": {

            "first_name": "John",
            "last_name": "Doe",
            "education": [
                {
                    "school": {
                        "name": "University of California, Berkeley"
                    },
                }
            ]
        }
    }
    response = get_common_education(common_education_no_date_payload, client_sdr.id).get("response")
    assert response == "John Doe attended University of California, Berkeley. I attended University of California, Berkeley from 2016 to 2020."

