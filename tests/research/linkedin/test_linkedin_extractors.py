from app import app
from decorators import use_app_context
from test_utils import (
    test_app
)

from src.research.linkedin.extractors.experience import (
    get_years_of_experience,
)

@use_app_context
def test_get_years_of_experience():
    many_yrs_data = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "end": {
                            "month": 1,
                            "year": 2019
                        },
                        "start": {
                            "month": 1,
                            "year": 2000
                        }
                    },
                    "profile_positions": [
                        {
                            "description": "description",
                            "title": "title"
                        }
                    ]
                },
                {
                    "date": {
                        "end": {
                            "month": 1,
                            "year": 2000
                        },
                        "start": {
                            "month": 1,
                            "year": 1999
                        }
                    },
                    "profile_positions": [
                        {
                            "description": "description",
                            "title": "title"
                        }
                    ]
                }
            ]
        }
    }
    response = get_years_of_experience(many_yrs_data)
    assert response["response"] == "20+ years of experience in industry"

    zero_yrs_data = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "end": {
                            "month": 11,
                            "year": 2019
                        },
                        "start": {
                            "month": 1,
                            "year": 2019
                        }
                    },
                    "profile_positions": [
                        {
                            "description": "description",
                            "title": "title"
                        }
                    ]
                },
            ]
        }
    }
    response = get_years_of_experience(zero_yrs_data)
    assert response["response"] == ""

    one_yr_data = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "end": {
                            "month": 11,
                            "year": 2020
                        },
                        "start": {
                            "month": 1,
                            "year": 2019
                        }
                    },
                    "profile_positions": [
                        {
                            "description": "description",
                            "title": "title"
                        }
                    ]
                },
            ]
        }
    }
    response = get_years_of_experience(one_yr_data)
    assert response["response"] == "1 year of experience in industry"