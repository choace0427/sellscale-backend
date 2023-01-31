import datetime
import mock
import json


@mock.patch(
    "src.research.linkedin.extractors.recommendations.get_completion",
    return_value="testing response",
)
@mock.patch(
    "src.research.linkedin.extractors.experience.get_current_month", return_value=1
)
@mock.patch(
    "src.research.linkedin.extractors.experience.get_current_year", return_value=2023
)
def test_get_recent_recommendation_summary(
    year_patch, month_patch, get_completion_patch
):
    from src.research.linkedin.extractors.experience import (
        get_years_of_experience_at_current_job,
    )

    edge_case_month_wrap = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2022, "month": 12},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(edge_case_month_wrap)
    assert data["response"] == "Just started at SellScale."

    edge_case_year_wrap = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2021, "month": 12},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(edge_case_year_wrap)
    assert data["response"] == "Had a recent 1-year anniversary at SellScale."

    anniversary_within_1_month = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2022, "month": 2},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(anniversary_within_1_month)
    assert data["response"] == "1-year anniversary at SellScale is coming up."

    anniversary_2_months_past = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2022, "month": 1},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(anniversary_2_months_past)
    assert data["response"] == "Had a recent 1-year anniversary at SellScale."

    less_than_5_months = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2022, "month": 10},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(less_than_5_months)
    assert data["response"] == "Just started at SellScale."

    half_a_year = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2022, "month": 7},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(half_a_year)
    assert data["response"] == "Been at SellScale for half a year."

    over_a_year = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2021, "month": 10},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(over_a_year)
    assert data["response"] == "Been at SellScale for over a year."

    half_a_decade = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2017, "month": 7},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(half_a_decade)
    assert data["response"] == "Been at SellScale for over half a decade."

    nearly_a_decade = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2013, "month": 7},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(nearly_a_decade)
    assert data["response"] == "Been at SellScale for nearly a decade."

    over_a_decade = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 2010, "month": 7},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(over_a_decade)
    assert data["response"] == "Been at SellScale for over a decade."

    over_five_decades = {
        "personal": {
            "position_groups": [
                {
                    "date": {
                        "start": {"year": 1960, "month": 7},
                        "end": {"year": None, "month": None},
                    }
                }
            ]
        },
        "company": {"details": {"name": "SellScale"}},
    }
    data = get_years_of_experience_at_current_job(over_five_decades)
    assert data["response"] == "Been at SellScale for over 6 decades."
