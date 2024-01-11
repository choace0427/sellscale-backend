from typing import Optional
from app import db
import requests


def get_contacts(
    num_contacts: int = 100,
    person_titles: list = [],
    person_not_titles: list = [],
    q_person_title: str = "",
    q_person_name: str = "",
    organization_industry_tag_ids: list = [],
    organization_num_employees_ranges: Optional[list] = None,
    person_locations: list = [],
    organization_ids: Optional[None] = None,
    revenue_range: dict = {"min": None, "max": None},
    organization_latest_funding_stage_cd: list = [],
    currently_using_any_of_technology_uids: list = [],
    event_categories: Optional[list] = None,
    published_at_date_range: Optional[dict] = None,
    person_seniorities: Optional[list] = None,
):
    breadcrumbs = None  # grab from first result
    partial_results_only = None  # grab from first result
    disable_eu_prospecting = None  # grab from first result
    partial_results_limit = None  # grab from first result
    pagination = {}  # grab from last result but sum the "per_page"

    per_page = 0

    contacts = []
    people = []

    for page in range(1, num_contacts // 100 + 1):
        try:
            response = get_contacts_for_page(
                page,
                person_titles,
                person_not_titles,
                q_person_title,
                q_person_name,
                organization_industry_tag_ids,
                organization_num_employees_ranges,
                person_locations,
                organization_ids,
                revenue_range,
                organization_latest_funding_stage_cd,
                currently_using_any_of_technology_uids,
                event_categories,
                published_at_date_range,
                person_seniorities,
            )

            print(
                "Found {} contacts".format(
                    len(response["contacts"] + response["people"])
                )
            )

            per_page += len(response["contacts"] + response["people"])

            if page == 1:
                breadcrumbs = response["breadcrumbs"]
                partial_results_only = response["partial_results_only"]
                disable_eu_prospecting = response["disable_eu_prospecting"]
                partial_results_limit = response["partial_results_limit"]

            contacts += response["contacts"]
            people += response["people"]

            pagination = response["pagination"]
            pagination["per_page"] = per_page
        except:
            continue

        if page > pagination.get("total_pages", 0):
            break

    return {
        "breadcrumbs": breadcrumbs,
        "partial_results_only": partial_results_only,
        "disable_eu_prospecting": disable_eu_prospecting,
        "partial_results_limit": partial_results_limit,
        "pagination": pagination,
        "contacts": contacts,
        "people": people,
    }


def get_contacts_for_page(
    page: int,
    person_titles: list = [],
    person_not_titles: list = [],
    q_person_title: str = "",
    q_person_name: str = "",
    organization_industry_tag_ids: list = [],
    organization_num_employees_ranges: Optional[list] = None,
    person_locations: list = [],
    organization_ids: Optional[None] = None,
    revenue_range: dict = {"min": None, "max": None},
    organization_latest_funding_stage_cd: list = [],
    currently_using_any_of_technology_uids: list = [],
    event_categories: Optional[list] = None,
    published_at_date_range: Optional[dict] = None,
    person_seniorities: Optional[list] = None,
):
    data = {
        "api_key": "F51KjDxCgbbC42h0-ovEDQ",
        "page": page,
        "per_page": 100,
        "person_titles": person_titles,
        "person_not_titles": person_not_titles,
        "q_person_title": q_person_title,
        "q_person_name": q_person_name,
        "organization_industry_tag_ids": organization_industry_tag_ids,
        "organization_num_employees_ranges": organization_num_employees_ranges,
        "person_locations": person_locations,
        "organization_ids": organization_ids,
        "revenue_range": revenue_range,
        "organization_latest_funding_stage_cd": organization_latest_funding_stage_cd,
        "currently_using_any_of_technology_uids": currently_using_any_of_technology_uids,
        "event_categories": event_categories,
        "published_at_date_range": published_at_date_range,
        "person_seniorities": person_seniorities,
    }

    response = requests.post("https://api.apollo.io/v1/mixed_people/search", json=data)

    return response.json()
