from app import app
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    test_app
)

from src.research.linkedin.extractors.experience import (
    get_years_of_experience,
    get_linkedin_bio_summary
)
from src.ml.openai_wrappers import OPENAI_COMPLETION_DAVINCI_3_MODEL
import mock

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


@use_app_context
@mock.patch("src.research.linkedin.extractors.experience.wrapped_create_completion", return_value="test")
def test_get_linkedin_bio_summary(mock_wrapped_create_completion):
    good_data = {
        "personal": {
            "summary": "test-summary",
            "first_name": "test-first-name",
            "last_name": "test-last-name",
        }
    }
    response = get_linkedin_bio_summary(good_data)
    assert response["response"] == "test"
    assert mock_wrapped_create_completion.call_count == 1
    assert mock_wrapped_create_completion.called_with(
        model=OPENAI_COMPLETION_DAVINCI_3_MODEL,
        prompt="individual: test-first-name test-last-name\nbio: test-summary\n\ninstruction: Summarize the individual's bio in 30 words or less.\n\nsummary:",
        max_tokens=30,
    )

    no_summary_data = {
        "personal": {
            "first_name": "test-first-name",
            "last_name": "test-last-name",
        }
    }
    response = get_linkedin_bio_summary(no_summary_data)
    assert response["response"] == ""

    no_name_data = {
        "personal": {
            "summary": "test-summary",
        }
    }
    response = get_linkedin_bio_summary(no_name_data)
    assert response["response"] == ""
