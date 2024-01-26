import json
from typing import Optional
from app import db
import requests

from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.utils.abstract.attr_utils import deep_get

ALLOWED_FILTERS = {
    "query_full_name": {
        "summary": "(str) Name of the person",
        "output_type": "string",
        "prompt": "Extract the name of the person from the query",
    },
    "included_title_keywords": {
        "summary": "(list) List of titles to include",
        "output_type": "list",
        "prompt": "Extract the titles to include from the query. Also include any permutations or synonyms of the titles in the output.",
    },
    "excluded_title_keywords": {
        "summary": "(list) List of titles to exclude",
        "output_type": "list",
        "prompt": "Extract the titles to exclude from the query. Also include any permutations or synonyms of the titles in the output.",
    },
    "query_titles": {
        "summary": "(str) List of titles to include",
        "output_type": "string",
        "prompt": "Extract the titles to include from the query. The syntax includes AND, OR, and NOT. Include quotation marks around titles in the query with spaces.",
    },
    "included_seniority_keywords": {
        "summary": "(list) List of seniorities to include",
        "output_type": "list",
        "prompt": "Extract the seniorities to include from the query. The allowed values are: 'owner', 'founder', 'c_suite', 'partner', 'vp', 'head', 'director', 'manager'. 'senior', 'entry', 'intern'",
    },
    "excluded_seniority_keywords": {
        "summary": "(list) List of seniorities to exclude",
        "output_type": "list",
        "prompt": "Extract the seniorities to exclude from the query. The allowed values are: 'owner', 'founder', 'c_suite', 'partner', 'vp', 'head', 'director', 'manager'. 'senior', 'entry', 'intern'",
    },
    "included_industries_keywords": {
        "summary": "(list) List of industries to include",
        "output_type": "list",
        "prompt": "Extract the industries to include from the query. Also include any permutations or synonyms of the industries in the output.",
    },
    "excluded_industries_keywords": {
        "summary": "(list) List of industries to exclude",
        "output_type": "list",
        "prompt": "Extract the industries to exclude from the query. Also include any permutations or synonyms of the industries in the output.",
    },
    "included_company_keywords": {
        "summary": "(list) List of companies to include",
        "output_type": "list",
        "prompt": "Extract the companies to include from the query. Also include any permutations or synonyms of the companies in the output.",
    },
    "excluded_company_keywords": {
        "summary": "(list) List of companies to exclude",
        "output_type": "list",
        "prompt": "Extract the companies to exclude from the query. Also include any permutations or synonyms of the companies in the output.",
    },
    "included_education_keywords": {
        "summary": "(list) List of schools to include",
        "output_type": "list",
        "prompt": "Extract the schools to include from the query. Also include any permutations or synonyms of the schools in the output.",
    },
    "excluded_education_keywords": {
        "summary": "(list) List of schools to exclude",
        "output_type": "list",
        "prompt": "Extract the schools to exclude from the query. Also include any permutations or synonyms of the schools in the output.",
    },
    "included_bio_keywords": {
        "summary": "(list) List of bio keywords to include",
        "output_type": "list",
        "prompt": "Extract the bio keywords to include from the query. Also include any permutations or synonyms of the bio keywords in the output.",
    },
    "excluded_bio_keywords": {
        "summary": "(list) List of bio keywords to exclude",
        "output_type": "list",
        "prompt": "Extract the bio keywords to exclude from the query. Also include any permutations or synonyms of the bio keywords in the output.",
    },
    "included_location_keywords": {
        "summary": "(list) List of locations to include",
        "output_type": "list",
        "prompt": "Extract the locations to include from the query. Also include any permutations or synonyms of the locations in the output.",
    },
    "excluded_location_keywords": {
        "summary": "(list) List of locations to exclude",
        "output_type": "list",
        "prompt": "Extract the locations to exclude from the query. Also include any permutations or synonyms of the locations in the output.",
    },
    "included_skills_keywords": {
        "summary": "(list) List of skills to include",
        "output_type": "list",
        "prompt": "Extract the skills to include from the query. Also include any permutations or synonyms of the skills in the output.",
    },
    "excluded_skills_keywords": {
        "summary": "(list) List of skills to exclude",
        "output_type": "list",
        "prompt": "Extract the skills to exclude from the query. Also include any permutations or synonyms of the skills in the output.",
    },
    "years_of_experience_start": {
        "summary": "(int) Years of experience to start",
        "output_type": "integer",
        "prompt": "Extract the years of experience to start from the query. The value should be an integer.",
    },
    "years_of_experience_end": {
        "summary": "(int) Years of experience to end",
        "output_type": "integer",
        "prompt": "Extract the years of experience to end from the query. The value should be an integer.",
    },
    "included_fundraise": {
        "summary": "(list) List of fundraise to include",
        "output_type": "list",
        "prompt": "Extract the fundraise to include from the query. The allowed values are: '0', '1', '10', '2', '3', '4', '5', '6', '7', '13', '14', '15', '11', '12'. The mapping is as follows:\n'Seed' - 0, 'Angel' - 1, 'Venture (Round not specified)' - 10, 'Series A' - 2, 'Series B' - 3, 'Series C' - 4, 'Series D' - 5, 'Series E' - 6, 'Series F' - 7, 'Debt Financing' - 13, 'Equity Crowdfunding' - 14, 'Convertible Note' - 15, 'Private Equity' - 11, 'Other' - 12",
    },
    "included_company_size": {
        "summary": "(list) List of company sizes to include",
        "output_type": "list",
        "prompt": "Extract the company sizes to include from the query. The allowed values are: '1,10','11,20','21,50','51,100','101,200','201,500','501,1000','1001,2000','2001,5000','5001,10000','10001'",
    },
    "included_revenue": {
        "summary": "(dict) Range of revenue to include",
        "output_type": "dict",
        "prompt": "Extract the revenue to include from the query. The value should be a dictionary with keys 'min' and 'max' and values as integers.",
    },
    "included_technology": {
        "summary": "(list) List of technologies to include",
        "output_type": "list",
        "prompt": "Extract the technologies to include from the query. Also include any permutations or synonyms of the technologies in the output.",
    },
    "included_news_event_type": {
        "summary": "(list) List of news event types to include",
        "output_type": "list",
        "prompt": "Extract the news event types to include from the query. The allowed values are: 'leadership', 'acquisition', 'expansion', 'new_offering', 'investment', 'cost_cutting', 'partnership', 'recognition', 'contract', 'corporate_challenges', 'relational'",
    },
}


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
    q_organization_search_list_id: Optional[str] = None,
    organization_department_or_subdepartment_counts: Optional[list] = None,
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
                q_organization_search_list_id,
                organization_department_or_subdepartment_counts,
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
    q_organization_search_list_id: Optional[str] = None,
    organization_department_or_subdepartment_counts: Optional[dict] = None,
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
        "q_organization_search_list_id": q_organization_search_list_id,
        "organization_department_or_subdepartment_counts": organization_department_or_subdepartment_counts,
    }

    response = requests.post("https://api.apollo.io/v1/mixed_people/search", json=data)

    return response.json()


def predict_filters_types_needed(query: str) -> list:
    prompt = """
    Referring to the query provided, return a list of which filters will be needed to get the results from the query.

    Query: "{query}"

    Filters:
    {filters_names_with_descriptions}

    Important: Return the filters as a JSON object formatted with key "filters": [ ... ]
    Important: ONLY respond with the JSON object, do not include any other text in the response.

    Filters needed:""".format(
        query=query,
        filters_names_with_descriptions="\n".join(
            [
                "{filter_name}: {filter_description}".format(
                    filter_name=filter_name,
                    filter_description=filter_details["summary"],
                )
                for filter_name, filter_details in ALLOWED_FILTERS.items()
            ]
        ),
    )

    completion = wrapped_chat_gpt_completion(
        messages=[{"role": "user", "content": prompt}], max_tokens=300, model="gpt-4"
    )

    data = json.loads(completion)

    return data["filters"]


def predict_filters_needed(query: str) -> dict:
    filter_types = predict_filters_types_needed(query)

    overall_filters = {}

    for filter_type in filter_types:
        instruction = deep_get(
            ALLOWED_FILTERS,
            "{filter_type}.prompt".format(filter_type=filter_type),
        )
        output_type = deep_get(
            ALLOWED_FILTERS,
            "{filter_type}.output_type".format(filter_type=filter_type),
        )

        if not instruction or not output_type:
            continue

        completion = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": "You are extracting data from the query. Follow the instructions carefully.\n\nQuery: {query}\n\nFilter Name: {filter_name}\n\nInstruction:\n{instruction}\nOutput Type: {output_type}\n\nImportant: Return the output as a JSON with the key 'data': and value in the given format\n\nOutput:".format(
                        query=query,
                        filter_name=filter_type,
                        instruction=instruction,
                        output_type=output_type,
                    ),
                }
            ],
            max_tokens=300,
            model="gpt-4",
        )

        data = json.loads(completion)

        overall_filters[filter_type] = data["data"]

    return overall_filters