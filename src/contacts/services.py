import json
from flask import jsonify
import yaml
import os
from typing import Dict, List, Optional
from app import db, app, celery
import requests
from src.apollo.controllers import fetch_tags
from src.apollo.services import get_apollo_cookies, get_fuzzy_company_list
from src.client.models import ClientArchetype, ClientSDR
from src.company.models import Company
from src.company.services import find_company_name_from_url
from src.contacts.models import SavedApolloQuery

from src.ml.openai_wrappers import DEFAULT_TEMPERATURE, wrapped_chat_gpt_completion
from src.ml.services import simple_perplexity_response
from src.prospecting.controllers import add_prospect_from_csv_payload
from src.prospecting.models import ProspectUploadSource
from src.utils.abstract.attr_utils import deep_get
from datetime import datetime

import concurrent.futures

from src.utils.hasher import generate_uuid

# APOLLO CREDENTIALS (SESSION and XCSRF are reverse engineered tokens, may require manual refreshing periodically)
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY")


# filters_schema = {
#     "name": "filters_schema",
#     "strict": True,
#     "schema": {
#         "type": "object",
#         "properties": {
#             "filters": {
#                 "type": "array",
#                 "items": {
#                     "type": "string"
#                 },
#                 "description": "List of filters needed for the query."
#             }
#         },
#         "required": ["filters"],
#         "additionalProperties": False
#     }
# }

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

ALLOWED_FILTERS_APOLLO = {
    "currently_using_any_of_technology_uids": {
        "summary": "(list) List of technologies that are used by this segment of people",
        "prompt": "Extract the technology UIDs currently in use from the query."
    },
    "event_categories": {
        "summary": "(list) List of event categories i.e. news event types, for example, ['leadership', 'acquisition']",
        "prompt": "Relate these event types to the query ask. The values should be one or more of these: 'leadership', 'acquisition', 'expansion', 'new_offering', 'investment', 'cost_cutting', 'partnership', 'recognition', 'contract', 'corporate_challenges', 'relational'."
    },
    "person_seniorities": {
        "summary": "(list) List of job title seniorities to include",
        "prompt": "Extract the seniorities to include from the query. The allowed values are: 'owner', 'founder', 'c_suite', 'partner', 'vp', 'head', 'director', 'manager', 'senior', 'entry', 'intern'"
    },
    "organization_latest_funding_stage_cd": {
        "summary": "(list) List of organization last funding stage codes, for example, ['0', '1', '2']",
        "prompt": "Extract the organization last funding stage codes from the query. The values should be a list of strings. The options are: Seed:'0', Angel:'1', Venture:'10', Series A:'2', Series B:'3', Series C:'4', Series D:'5', Series E:'6', Series F:'7', Debt Financing:'13', Equity Crowdfunding:'14', Convertible Note:'15', Private Equity:'11', Other:'12'. The values should be the only values, do not include the labels at all. e.g. ['0', '1', '2']"
    },
    "person_locations": {
        "summary": "(list) List of person locations",
        "prompt": "Extract the person locations from the query. The values should be a list of strings, strictly, the choice should be one or more of these (if applicable): ['United States', 'Europe', 'Germany', 'India', 'United Kingdom', 'France', 'Canada', 'Australia']"
    },
    "person_titles": {
        "summary": "(list) List of person titles. Please always include this",
        "prompt": "Infer some job title keywords from this sales segment. The values should be a list of strings. IMPORTANT: Job title keywords should NOT contain seniority. (Seniority, eg 'manager', is already captured in another section). For example, instead of 'Marketing Manager' or 'VP Business Development', you'd write 'Marketing' or 'Business Development'. Be clever and come up with 7 related job title keywords that may be synonymous with my target audience. Not plural. Also don't be too specific, i.e. VP of clinical affairs is too specific, Clinical Affairs is better. Do not include the word manager. Only output the list of strings."
    },
    "published_at_date_range": {
        "summary": "(dict) Date range for company news",
        "prompt": "Extract the date range for published content from the query. The value should be a dictionary with a 'min' as a string, exclusively with '_days_ago' post-pended. eg {'min': '30_days_ago'}"
    },
    "q_person_name": {
        "summary": "(str) Person name query",
        "prompt": "Extract the person name query from the query. The value should be a string."
    },
    "revenue_range": {
        "summary": "(dict) Range of revenue",
        "prompt": "The query you are given is describing a sales segment. Be clever and come up with a likely revenue range from the query, for this sales segment. The value should be a dictionary with keys 'min' and 'max' and values as integers. The values should be reasonable, only the object. e.g. {'min': 5000000, 'max': 10000000}"
    }
}

MEGA_FILTERS_SCHEMA_APOLLO = {
    "name": "mega_filters_schema",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "technology_uids": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of technology UIDs currently in use."
            },
            "event_categories": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of event categories relevant to the query."
            },
            "person_seniorities": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of job title seniorities to include."
            },
            "organization_latest_funding_stage_cd": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of organization last funding stage codes."
            },
            "person_locations": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of person locations."
            },
            "person_titles": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of person titles."
            },
            "published_at_date_range": {
                "type": "object",
                "properties": {
                    "min": {
                        "type": "string"
                    }
                },
                "additionalProperties": False,
                "description": "Date range for published content."
            },
            "q_person_name": {
                "type": "string",
                "description": "Person name query."
            },
            "revenue_range": {
                "type": "object",
                "properties": {
                    "min": {
                        "type": "integer"
                    },
                    "max": {
                        "type": "integer"
                    }
                },
                "required": ["min", "max"],
                "additionalProperties": False,
                "description": "Range of revenue."
            }
        },
        "additionalProperties": False,
    }
}



def get_contacts_from_predicted_query_filters(query: str, retries=3):
    try:
        filters = predict_filters_needed(query)
        contacts = apollo_get_contacts(
            client_sdr_id=1,
            num_contacts=100,
            person_titles=filters.get("included_title_keywords", []),
            person_not_titles=filters.get("excluded_title_keywords", []),
            organization_num_employees_ranges=filters.get(
                "included_company_size",
                [
                    "1,10",
                    "11,20",
                    "21,50",
                    "51,100",
                    "101,200",
                    "201,500",
                    "501,1000",
                    "1001,2000",
                    "2001,5000",
                    "5001,10000",
                    "10001",
                ],
            ),
            person_locations=filters.get("included_location_keywords", []),
            revenue_range=filters.get(
                "included_revenue",
                {
                    "min": filters.get("revenue_min", None),
                    "max": filters.get("revenue_max", None),
                },
            ),
            organization_latest_funding_stage_cd=filters.get("included_fundraise", []),
            person_seniorities=filters.get("included_seniority_keywords", []),
            is_prefilter=False,
        )
        return contacts
    except Exception as e:
        if retries > 0:
            return get_contacts_from_predicted_query_filters(query, retries=retries - 1)
        else:
            raise e
@celery.task
def add_companies_to_db(company_names, organization_ids):
    companies_to_add = []
    existing_companies = {c.apollo_uuid: c for c in Company.query.filter(Company.apollo_uuid.in_(organization_ids)).all()}
    
    for company_name, organization_id in zip(company_names, organization_ids):
        if organization_id in existing_companies:
            existing_companies[organization_id].name = company_name
        else:
            companies_to_add.append(Company(name=company_name, apollo_uuid=organization_id))
    
    if companies_to_add:
        db.session.bulk_save_objects(companies_to_add)
        db.session.commit()
    return


def apollo_get_contacts(
    client_sdr_id: int,
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
    is_prefilter: bool = False,
    q_organization_keyword_tags: Optional[list] = None,
    filter_name: Optional[str] = None,
    segment_description: Optional[str] = None,
    value_proposition: Optional[str] = None,
    saved_apollo_query_id: Optional[int] = None,
    is_icp_filter: Optional[bool] = False,
):
    breadcrumbs = None  # grab from first result
    partial_results_only = None  # grab from first result
    disable_eu_prospecting = None  # grab from first result
    partial_results_limit = None  # grab from first result
    pagination = {}  # grab from last result but sum the "per_page"

    per_page = 0

    saved_query_id = None
    contacts = []
    people = []
    data = {}

    for page in range(1, num_contacts // 100 + 1):
        try:
            response, data, saved_query_id = apollo_get_contacts_for_page(
                client_sdr_id,
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
                is_prefilter=is_prefilter,
                q_organization_keyword_tags=q_organization_keyword_tags,
                filter_name=filter_name,
                segment_description=segment_description,
                value_proposition=value_proposition,
                is_icp_filter=is_icp_filter,
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

    contacts = add_match_reasons(contacts, breadcrumbs)
    people = add_match_reasons(people, breadcrumbs)

    # if saved_apollo_query_id (one we want to be editing), update the query data in the DB and delete the old one
    if saved_apollo_query_id:
        temp_saved_query: SavedApolloQuery = SavedApolloQuery.query.get(saved_query_id)  # this is like a temporary object
        saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.filter_by(id=saved_apollo_query_id).first()  # object we want to modify

        # commented ones should stay the same

        # saved_apollo_query.client_sdr_id = saved_query.client_sdr_id
        # saved_apollo_query.custom_name = saved_query.custom_name
        # saved_apollo_query.value_proposition = saved_query.value_proposition
        # saved_apollo_query.segment_description = saved_query.segment_description
        saved_apollo_query.name_query = temp_saved_query.name_query
        saved_apollo_query.data = temp_saved_query.data
        saved_apollo_query.results = temp_saved_query.results
        saved_apollo_query.is_prefilter = True
        saved_apollo_query.num_results = temp_saved_query.num_results
        db.session.commit()  # commit the changes to the non-temp object
        db.session.delete(temp_saved_query)  # optionally delete the old query here.
        db.session.commit()

        print("Updated the saved query with ID", saved_apollo_query_id, 'and deleted the old one. with id', saved_query_id)

    return {
        "breadcrumbs": breadcrumbs,
        "partial_results_only": partial_results_only,
        "disable_eu_prospecting": disable_eu_prospecting,
        "partial_results_limit": partial_results_limit,
        "pagination": pagination,
        "contacts": contacts,
        "people": people,
        "saved_query_id": saved_apollo_query_id if saved_apollo_query_id else saved_query_id,
        "data": data,
    }


def add_match_reasons(
    contacts: list,
    breadcrumbs: list,
):
    for contact in contacts:
        match_reasons = []
        for breadcrumb in breadcrumbs:
            if (
                breadcrumb["signal_field_name"] == "person_titles"
                and contact["title"]
                and breadcrumb["value"]
                and breadcrumb["value"] in contact["title"].lower()
            ):
                match_reasons.append(
                    {"label": breadcrumb["label"], "value": breadcrumb["value"]}
                )
            if breadcrumb["signal_field_name"] == "person_locations":
                try:
                    if (
                        contact["country"]
                        and breadcrumb["value"] in contact["country"].lower()
                    ):
                        match_reasons.append(
                            {"label": breadcrumb["label"], "value": breadcrumb["value"]}
                        )
                    if (
                        contact["state"]
                        and breadcrumb["value"] in contact["state"].lower()
                    ):
                        match_reasons.append(
                            {"label": breadcrumb["label"], "value": breadcrumb["value"]}
                        )
                    if (
                        contact["city"]
                        and breadcrumb["value"] in contact["city"].lower()
                    ):
                        match_reasons.append(
                            {"label": breadcrumb["label"], "value": breadcrumb["value"]}
                        )
                except:
                    pass

        contact["match_reasons"] = match_reasons

    return contacts


def apollo_get_contacts_for_page(
    client_sdr_id: int,
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
    is_prefilter: bool = False,
    q_organization_keyword_tags: Optional[list] = None,
    filter_name: Optional[str] = None,
    segment_description: Optional[str] = None,
    value_proposition: Optional[str] = None,
    is_icp_filter: Optional[bool] = False,
):
    data = {
        "api_key": APOLLO_API_KEY,
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
        "q_organization_keyword_tags": q_organization_keyword_tags,
    }

    response = requests.post("https://api.apollo.io/v1/mixed_people/search", json=data)
    results = response.json()

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    name = "unknown"
    if client_sdr:
        name = client_sdr.name

    formatted_date = datetime.now().strftime("%b %d %Y %H:%M:%S")
    hash = generate_uuid(base=f"{name} {formatted_date}")[0:6]

    saved_query = SavedApolloQuery(
        is_icp_filter=is_icp_filter,
        custom_name=filter_name,
        value_proposition=value_proposition,
        segment_description=segment_description,
        name_query=f"[{name}] Query on {formatted_date} [{hash}]",
        data=data,
        results=results,
        client_sdr_id=client_sdr_id,
        is_prefilter=is_prefilter,
        num_results=results.get("pagination", {}).get("total_entries", 0),
    )
    db.session.add(saved_query)
    db.session.commit()
    saved_query_id = saved_query.id

    return results, data, saved_query_id


def apollo_get_organizations(
    client_sdr_id: int,
    company_names: list[str] = [],
    company_urls: list[str] = [],
    company_prompt: str = "",
) -> list:
    """A near-pass-through function which will collect organization objects from Apollo based on the company names provided.

    Args:
        company_names (list[str]): List of company names to search for
        company_urls (list[str]): List of company URLs to search for

    Returns:
        list: List of organization objects
    """
    # Get organizations from company names
    data: list = []

    if company_prompt:
        company_prompt = company_prompt + "  Return the company names in bullet point form."
        perplexity_response = simple_perplexity_response("llama-3-sonar-large-32k-online", company_prompt)[0]
        chatgpt_response = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You will be given a prompt containing a list of current companies. I want you to extract "
                               "it and return it in a json format, with one object with the key 'company_names'. Additionally, just keep the names simple. Do not add 'Inc.' or 'Corporated' or other similar additions. For example, Apple Inc. is just Apple. Also, do not include anything else in your output. \nOutput:"},
                {
                    "role": "user",
                    "content": perplexity_response
                }],
            model="gpt-4o",
            max_tokens=1000
        )

        chatgpt_response = chatgpt_response.replace("`", "").replace("json", "")

        chatgpt_json = json.loads(chatgpt_response)
        stripped_names = chatgpt_json.get("company_names", [])

        if not company_names:
            company_names = stripped_names
        else:
            company_names.extend(stripped_names)

    if company_names:
        orgs = apollo_get_organizations_from_company_names(
            client_sdr_id=client_sdr_id,
            company_names=company_names,
        )
        data.extend(orgs)

    # Get organizations from company urls
    if company_urls:
        company_names = []
        # not_found_urls = []

        # Convert urls to company names using Company model
        # for company_url in company_urls:
        #     name = find_company_name_from_url(
        #         client_sdr_id=client_sdr_id, company_url=company_url
        #     )
        #     if name:
        #         company_names.append(name)
        #     else:
        #         not_found_urls.append(company_url)

        # Convert urls to company names using urllib
        urllib_names = get_company_name_using_urllib(urls=company_urls)
        company_names.extend(urllib_names)

        # Get organizations from company names
        orgs = apollo_get_organizations_from_company_names(
            client_sdr_id=client_sdr_id,
            company_names=company_names,
        )
        data.extend(orgs)

    # Deduplicate
    data = [dict(t) for t in {tuple(d.items()) for d in data}]

    return data


def get_company_name_using_urllib(urls: list[str]) -> list[str]:
    """Get the company name from a list of URLs using urllib. Hacky solution, but it works.

    Args:
        urls (list[str]): List of URLs to extract the company names from

    Returns:
        list[str]: List of company names
    """
    import re
    from urllib.parse import urlparse

    company_names = []

    for url in urls:
        try:
            # Parse the URL
            parsed_url = urlparse(url)

            # If this is something we can parse
            if parsed_url.netloc:
                # Remove 'www.' if present
                netloc = parsed_url.netloc.replace("www.", "")
                # Extract the domain name
                domain_parts = netloc.split(".")
                if len(domain_parts) > 2:
                    domain_name = ".".join(domain_parts[-2:])
                else:
                    domain_name = netloc
                domain_name = domain_name.title()
                domain_name = domain_name.split(".")[0]
                print("Using URLLIB", domain_name)
                company_names.append(domain_name)
            else:
                # Use regex to extract the domain name
                domain_name = re.search(
                    r"(?:https?://)?(?:www\.)?([^./]+(?:\.[^./]+)+)", url
                ).group(1)

                # Make the domain name title case
                domain_name = domain_name.title()
                domain_name = domain_name.split(".")[0]
                print("Using regex", domain_name)
                company_names.append(domain_name)
        except Exception as e:
            print("Error:", e)

    return company_names


def apollo_get_organizations_from_company_names(
    client_sdr_id: int,
    company_names: list[str],
) -> list:
    """A near-pass-through function which will collect organization objects from Apollo based on the company names provided.

    Args:
        client_sdr_id (int): SDR to tie this query to
        company_names (list[str]): List of company names to search for

    Returns:
        list: List of organization objects
    """
    cookies, csrf_token = get_apollo_cookies()

    # Set the headers
    headers = {
        "x-csrf-token": csrf_token,
        "cookie": cookies,
    }

    def apollo_org_search(company_name: str):
        print("Getting company data for", company_name)
        # Set the data
        data = {
            "q_organization_fuzzy_name": company_name,
            "display_mode": "fuzzy_select_mode",
        }

        # Make the request
        response = requests.post(
            "https://app.apollo.io/api/v1/organizations/search",
            headers=headers,
            json=data,
        )

        # Get the organizations and append the first one to the objects list
        try:
            organizations = response.json().get("organizations")
            if organizations and len(organizations) > 0:
                return organizations[0]
        except:
            print("ERROR", response.text)
        return None

    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(
            executor.map(
                apollo_org_search,
                company_names,
            )
        )

    # Remove NONE from the results
    results = [obj for obj in results if obj]

    # Save the query
    formatted_date = datetime.now().strftime("%b %d %Y %H:%M:%S")
    hash = generate_uuid(base=f"{formatted_date}")[0:6]
    saved_query = SavedApolloQuery(
        name_query=f"Company Fuzzy Search query on {formatted_date} [{hash}]",
        data={"company_names": company_names},
        results=results,
        client_sdr_id=client_sdr_id,
    )
    db.session.add(saved_query)
    db.session.commit()

    if results and len(results) > 0:
        from src.company.services import populate_company_from_apollo_result

        for result in results:
            company_id = populate_company_from_apollo_result.delay(result)
            print("Updated Company ID", company_id)

    return results


def apollo_get_pre_filters(
    client_sdr_id: int,
    persona_id: Optional[int] = None,
    segment_id: Optional[int] = None,
    saved_query_id: Optional[int] = None,
):
    if saved_query_id:
        query = f"""
            select data, results, saved_apollo_query.id
            from saved_apollo_query
            where saved_apollo_query.id = {saved_query_id}
            limit 1
        """
    else:
        query = f"""
            select data, results, persona.id "persona", saved_apollo_query.id
            from saved_apollo_query
            join client_sdr on client_sdr.id = saved_apollo_query.client_sdr_id
            left join persona on persona.saved_apollo_query_id = saved_apollo_query.id
            left join segment on segment.saved_apollo_query_id = saved_apollo_query.id
            where client_sdr.id = {client_sdr_id}
            and (
                ({persona_id != None} and persona.id = {persona_id or 'null'})
                or ({segment_id != None} and segment.id = {segment_id or 'null'})
                or ({segment_id == None} and {persona_id == None} and
                saved_apollo_query.is_prefilter
                )
            )
            order by saved_apollo_query.created_at desc
            limit 1
        """

    d_results = []
    results = db.engine.execute(query).fetchall()
    for row in results:
        if (saved_query_id):
            data, results, query_id = row
            persona_id = None
            segment_id = None
        else:
            (
                data,
                results,
                persona_id,
                query_id,
            ) = row
        d_results.append(
            {
                "data": data,
                # "results": results,
                "persona_id": persona_id,
                "query_id": query_id,
            }
        )
    query_data = d_results[0] if d_results and len(d_results) > 0 else None

    org_ids = query_data.get("data", {}).get("organization_ids", [])

    from src.company.services import find_company
    from src.company.models import Company

    company_ids = []
    if org_ids:
        for org_id in org_ids:
            company_id = find_company(client_sdr_id=client_sdr_id, apollo_uuid=org_id)
            if company_id:
                company_ids.append(company_id)

    companies: list[Company] = Company.query.filter(
        Company.id.in_([id for id in company_ids if id is not None]),
    ).all()

    return {
        "data": query_data,
        "companies": [company.to_dict() for company in companies],
    }

def get_technology_uids(query: str) -> list:
    #ingest the prompt and come up with
    #at most 5 relevant technologies that might be used
    def get_data(query):
        completion = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": "Here is a user query: {query}, based on that, please give me a python list of one word short strings of at most 7 different technologies that could be used by this market segment. They can be specific, please return only the python list".format(
                        query=query,
                    ),
                }
            ],
            max_tokens=100,
            model="gpt-4o",
        )
        completion = completion.replace("`", "").replace("python", "").replace('json','')
        data = yaml.safe_load(completion)
        return data

    attempts = 0
    data = []
    while attempts < 3:
        try:
            data = get_data(query)
            break
        except:
            attempts += 1
            if attempts == 3:
                data = []
                break

    ret = []
    for technology in data:
        uids = get_fuzzy_company_list(technology)
        if uids:
            response_json = uids.json()
            if len(response_json.get('tags', [])) > 1:
                ret.append(response_json['tags'][0]['uid'])
    return ret

def get_industry_tag_ids(query: str) -> list:
    # Validate it's a list
    def get_data(query):
        completion = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": "Here is a user conversation: {query}, please give me a python list of one word short strings of at most 7 different industries that may apply to this sales segment. They can be specific, please return only the python list".format(
                        query=query,
                    ),
                }
            ],
            max_tokens=100,
            model="gpt-4o",
        )
        completion = completion.replace("`", "").replace("python", "").replace('json','')
        data = yaml.safe_load(completion)
        return data

    attempts = 0
    data = []
    while attempts < 3:
        try:
            data = get_data(query)
            break
        except:
            attempts += 1
            if attempts == 3:
                data = []
                break
    if (len(data) == 0):
        return []
    tag_ids = []
    import concurrent.futures

    def process_query(query, cookies, csrf_token):
        tags = []
        last_successful_tags = []
        for i in range(1, len(query) + 1):
            partial_query = query[:i]
            try:
                response, status_code = fetch_tags(partial_query, (cookies, csrf_token))
            except ValueError as e:
                continue
            if status_code != 200:
                continue
            response_json = response.get("data", {})
            tags = response_json.get('tags', [])
            if len(tags) == 1:
                return tags[0]['id']
            if tags:
                last_successful_tags = tags
        if not tags and last_successful_tags :
            return last_successful_tags[0]['id']
        return None
    
    queries = data

    cookies, csrf_token = get_apollo_cookies()

    with app.app_context():
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda query: process_query(query, cookies, csrf_token), queries))

        tag_ids = [result for result in results if result is not None]
    return tag_ids

def get_company_ids(query: str, client_sdr_id: int) -> list:
    #loop through the data array
    tags = apollo_get_organizations(
        client_sdr_id=client_sdr_id,
        company_prompt='here is a sales segment. please give me the top companies related to it: ' + query
    )
    tag_ids_only = [tag['id'] for tag in tags]
    return tag_ids_only


def predict_filters_types_needed(query: str, use_apollo_filters=False) -> list:
    allowed_filters = ALLOWED_FILTERS_APOLLO if use_apollo_filters else ALLOWED_FILTERS
    filters_schema = {
        "name": "filters_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of filters needed for the query."
                }
            },
            "required": ["filters"],
            "additionalProperties": False
        }
    }

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
                for filter_name, filter_details in allowed_filters.items()
            ]
        ),
    )

    try:
        completion = wrapped_chat_gpt_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            model="gpt-4o-2024-08-06",
            response_format={"type": "json_schema", "json_schema": filters_schema}
        )
        #convert completion to json
        completion = json.loads(completion)
        data = completion.get("filters", [])
    except Exception as e:
        print('Error:', e)
        return []

    return data


def predict_filters_needed(query: str, use_apollo_filters=False, client_sdr_id: int = None) -> dict:
    allowed_filters = ALLOWED_FILTERS_APOLLO if use_apollo_filters else ALLOWED_FILTERS
    filter_types = predict_filters_types_needed(query, use_apollo_filters=use_apollo_filters)
    overall_filters = {}

    # Rebuild the filter_types array based on allowed_filters. sometimes the chat gpt response is not consisent
    filter_types_array_stringified = json.dumps(filter_types)

    rebuilt_filter_types = []
    for filter_key in allowed_filters.keys():
        if filter_key in filter_types_array_stringified:
            rebuilt_filter_types.append(filter_key)
    
    filter_types = rebuilt_filter_types


    print('use apollo filters', use_apollo_filters)

    print('predicted filter types needed:', filter_types)
    #always come up with some technology they might be using
    if use_apollo_filters:
        if "currently_using_any_of_technology_uids" in filter_types:
            technology_uids = get_technology_uids(query)
            overall_filters["currently_using_any_of_technology_uids"] = technology_uids
            #remove the technology_uids from the filter_types because the job is done.
            filter_types.remove("currently_using_any_of_technology_uids")

    if use_apollo_filters:
        if "organization_industry_tag_ids" in filter_types:
            #pass in the array of industry tags e.g. 
            industry_tags = get_industry_tag_ids(query)
            print('industry_tags', industry_tags)
            overall_filters["organization_industry_tag_ids"] = industry_tags
            filter_types.remove("organization_industry_tag_ids")

    if use_apollo_filters:
        if "organization_ids" in filter_types:
            print('getting company ids')
            #pass in the array of company names
            companies = get_company_ids(query, client_sdr_id)
            overall_filters["organization_ids"] = companies
            filter_types.remove("organization_ids")

    #for the remaining filters, we will use the chat gpt to get the data
    #first, pull out the fitlers that are not already in the overall_filters

    filter_schema = MEGA_FILTERS_SCHEMA_APOLLO
    # Adjust the schema to only include allowed filters
    allowed_properties = {k: v for k, v in filter_schema['schema']['properties'].items() if k in filter_types}
    print('allowed_properties', allowed_properties)

    filter_schema['schema']['properties'] = allowed_properties

    # Update the 'required' array to include only keys that are in allowed_properties
    filter_schema['schema']['required'] = list(allowed_properties.keys())

    # Prepare the instruction and schema for the GPT call
    instructions = [deep_get(allowed_filters, f"{filter_key}.prompt") for filter_key in filter_types]
    combined_instruction = " \n\n".join(instructions)


    # Perform a single GPT call with the adjusted schema
    completion = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": f"You are extracting data from the query. Follow the instructions carefully. \n\nQuery: {query}\n\nInstructions:\n{combined_instruction}\n\nOutput:",
            }
        ],
        max_tokens=300,
        model="gpt-4o-2024-08-06",
        response_format={"type": "json_schema", "json_schema": filter_schema}
    )

    # Process the GPT response
    data = json.loads(completion)
    overall_filters.update(data)
    return overall_filters


def get_territories(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    query = """
        with d as (
        select
            client_sdr.id,
            client_sdr.name,
            client_sdr.title,
            client_sdr.img_url,
            case when
                client_sdr.territory_name is null
                    then 'Not defined'
                else
                    client_sdr.territory_name
            end territory_name,
            max(saved_apollo_query.id) "saved_apollo_id"
        from client_sdr
            left join saved_apollo_query
                on saved_apollo_query.client_sdr_id = client_sdr.id and saved_apollo_query.is_prefilter = true
        where
            client_sdr.client_id = {client_id} and
            client_sdr.active
        group by 1,2,3,4,5
    )
    select
        d.*,
        saved_apollo_query.num_results
    from d
        left join saved_apollo_query on saved_apollo_query.id = d.saved_apollo_id;
    """

    data = db.session.execute(query.format(client_id=client_id))
    territories_raw = data.fetchall()

    territories = []
    for territory in territories_raw:
        territories.append(
            {
                "id": territory.id,
                "name": territory.name,
                "title": territory.title,
                "img_url": territory.img_url,
                "territory_name": territory.territory_name,
                "num_results": territory.num_results,
            }
        )

    return territories


def upload_prospects_from_apollo_page_to_segment(
    client_sdr_id: int,
    saved_apollo_query_id: int,
    page: int,
    segment_id: int,
):
    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.get(
        saved_apollo_query_id
    )
    payload = saved_apollo_query.data

    unassigned_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype,
    ).first()
    if not unassigned_archetype:
        return {"error": "No unassigned archetype found"}
    unassigned_archetype_id: int = unassigned_archetype.id

    # call apollo_get_contacts_for_page
    response, data, saved_query_id = apollo_get_contacts_for_page(
        client_sdr_id=client_sdr_id,
        page=page,
        person_titles=payload.get("person_titles", []),
        person_not_titles=payload.get("person_not_titles", []),
        q_person_title=payload.get("q_person_title", ""),
        q_person_name=payload.get("q_person_name", ""),
        organization_industry_tag_ids=payload.get("organization_industry_tag_ids", []),
        organization_num_employees_ranges=payload.get(
            "organization_num_employees_ranges", []
        ),
        person_locations=payload.get("person_locations", []),
        organization_ids=payload.get("organization_ids", None),
        revenue_range=payload.get("revenue_range", {"min": None, "max": None}),
        organization_latest_funding_stage_cd=payload.get(
            "organization_latest_funding_stage_cd", []
        ),
        currently_using_any_of_technology_uids=payload.get(
            "currently_using_any_of_technology_uids", []
        ),
        event_categories=payload.get("event_categories", None),
        published_at_date_range=payload.get("published_at_date_range", None),
        person_seniorities=payload.get("person_seniorities", None),
        q_organization_search_list_id=payload.get(
            "q_organization_search_list_id", None
        ),
        organization_department_or_subdepartment_counts=payload.get(
            "organization_department_or_subdepartment_counts", None
        ),
        is_prefilter=payload.get("is_prefilter", False),
        q_organization_keyword_tags=payload.get("q_organization_keyword_tags", None),
    )

    # get the contacts and people
    contacts = response["contacts"]
    people = response["people"]
    all_contacts = contacts + people

    # create a list of {first_name, last_name, linkedin_url}
    prospects = []
    for contact in all_contacts:
        prospects.append(
            {
                "first_name": contact.get("first_name", ""),
                "last_name": contact.get("last_name", ""),
                "linkedin_url": contact.get("linkedin_url", ""),
            }
        )

    # upload prospects
    msg, error_code = add_prospect_from_csv_payload(
        client_sdr_id=client_sdr_id,
        archetype_id=unassigned_archetype_id,
        csv_payload=prospects,
        allow_duplicates=True,
        source=ProspectUploadSource.CONTACT_DATABASE,
        segment_id=segment_id,
    )

    return {"msg": msg, "error_code": error_code}


def apollo_org_search(company_name: str):
    print("Getting company data for", company_name)

    cookies, csrf_token = get_apollo_cookies()

    # Set the headers
    headers = {
        "x-csrf-token": csrf_token,
        "cookie": cookies,
    }

    # Set the data
    data = {
        "q_organization_fuzzy_name": company_name,
        "display_mode": "fuzzy_select_mode",
    }

    # Make the request
    response = requests.post(
        "https://app.apollo.io/api/v1/organizations/search",
        headers=headers,
        json=data,
    )

    # Get the organizations and append the first one to the objects list
    try:
        organizations = response.json().get("organizations")
        if organizations and len(organizations) > 0:
            return organizations[0]
    except:
        print("ERROR", response.text)
    return None


def save_apollo_query(domain):
    # https://app.apollo.io/api/v1/organization_search_lists/save_query
    # {query: "dliagency.com↵apollo.io", cacheKey: 1718407246578}

    url = "https://app.apollo.io/api/v1/organization_search_lists/save_query"
    payload = {"query": domain, "cacheKey": 1719321279248}

    cookies, csrf_token = get_apollo_cookies()

    headers = {
        "x-csrf-token": csrf_token,
        "cookie": cookies,
    }

    response = requests.post(url, headers=headers, json=payload)
    print(response.text)

    return response.json()

def get_apollo_queries_under_sdr(client_sdr_id: int):
    
    #has a custom_name, for this new version
    queries: list[SavedApolloQuery] = SavedApolloQuery.query.filter(
        SavedApolloQuery.client_sdr_id == client_sdr_id,
        SavedApolloQuery.is_prefilter == True,
        SavedApolloQuery.custom_name.isnot(None)
    ).all()


    return [query.to_dict() for query in queries]


def handle_chat_icp(client_sdr_id: int, chat_content: list[dict], prompt: str) -> Dict[str, str]:
    """
    Generate sales segments and a friendly acknowledgment message based on chat content and the latest message,
    using a single chat GPT call with a defined schema to generate the required information.
    """

    system_message_response = {
        "role": "system",
        "content": (
            "You are an AI tasked with generating three key elements for a sales segment: "
            "a descriptive segment name, a detailed segment description, and a compelling segment's value proposition, "
            "along with a friendly acknowledgment message for the user.\n\n"
            "Ensure the segment description is clearly formatted. For instance:\n\n"
            "Bad Description Example:\n"
            "This segment targets passionate Coca-Cola enthusiasts who appreciate the brand's history, "
            "iconic products, and cultural impact. These individuals are not just casual drinkers; "
            "they are brand loyalists who enjoy exploring new flavors, participating in promotions, "
            "and engaging with Coca-Cola's marketing campaigns.\n\n"
            "Good Description Example:\n"
            "- Title keywords: Marketing, Client.\n"
            "- Seniority: Director+\n"
            "- Account: Advertising or marketing platforms.\n"
            "These companies optimize marketing/ad spend. They target big brands seeking optimization.\n"
            "Example companies: Zvnga, LG Ad Solutions.\n\n"
            "Value Proposition Examples:\n"
            "Bad: Unlock a world of exclusive Coca-Cola experiences, from limited-edition flavors to brand events.\n"
            "Good: They aim to access CMOs/marketing/advertising professionals, their main customer base.\n\n"
            "Segment Name Examples:\n"
            "Bad: Coca-Cola Connoisseurs\n"
            "Good: AdTech/MarTech Innovators\n\n"
            "In your friendly response, offer suggestions to refine the segment or provide constructive feedback. "
            "Please use the first person in your response."
        )
    }

    nicely_formatted_message_history_string = '\n'.join([f"{msg['sender']}: {msg.get('query', '')}" for msg in chat_content]) + "\nlast message from user: " + prompt
    nicely_formatted_message_history_string = nicely_formatted_message_history_string[-400:]  # clip this to only be the last 400 tokens

    chat_gpt_prompt = "here is the user's conversation history: \n" + nicely_formatted_message_history_string + "\n\n" + prompt + ' now please generate a clever and detailed new sales segment based on the conversation history and the latest message.'

    # Prepare the messages for the chat response
    messages = [system_message_response, {"role": "user", "content": chat_gpt_prompt}]

    sales_segment_schema = {
        "name": "sales_segment_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "segment_name": {"type": "string"},
                "segment_description": {"type": "string"},
                "segment_value_proposition": {"type": "string"},
                "friendly_acknowledgment": {"type": "string"}
            },
            "required": ["segment_name", "segment_description", "segment_value_proposition", "friendly_acknowledgment"],
            "additionalProperties": False
        }
    }

    try:
        response_content = wrapped_chat_gpt_completion(
            model='gpt-4o',
            messages=messages,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=500,
            response_format={"type": "json_schema", "json_schema": sales_segment_schema}
        )
        response_content = json.loads(response_content)
        segment_name = response_content.get("segment_name", "")
        segment_description = response_content.get("segment_description", "")
        segment_value_proposition = response_content.get("segment_value_proposition", "")
        friendly_acknowledgment = response_content.get("friendly_acknowledgment", "")
    except Exception as e:
        print('Error:', e)
        return {"response": "An error occurred while generating the sales segment.", "data": {}, "makers": "", "industry": "", "pain_point": "", "acknowledgment": ""}

    filters = predict_filters_needed('here is a user conversation: ' + nicely_formatted_message_history_string + ' given that conversation, please create the segment.', use_apollo_filters=True, client_sdr_id=client_sdr_id)

    data = apollo_get_contacts(
        filter_name=segment_name,
        segment_description=segment_description,
        value_proposition=segment_value_proposition,
        client_sdr_id=client_sdr_id,
        num_contacts=filters.get("num_contacts", 100),
        person_titles=filters.get("person_titles", []),
        person_not_titles=filters.get("person_not_titles", []),
        q_person_title=filters.get("q_person_title", ""),
        q_person_name=filters.get("q_person_name", ""),
        organization_industry_tag_ids=filters.get("organization_industry_tag_ids", []),
        organization_num_employees_ranges=filters.get("organization_num_employees_ranges", None),
        person_locations=filters.get("person_locations", []),
        organization_ids=filters.get("organization_ids", None),
        revenue_range=filters.get("revenue_range", {"min": None, "max": None}),
        organization_latest_funding_stage_cd=filters.get("organization_latest_funding_stage_cd", []),
        currently_using_any_of_technology_uids=filters.get("currently_using_any_of_technology_uids", []),
        event_categories=filters.get("event_categories", None),
        published_at_date_range=filters.get("published_at_date_range", None),
        person_seniorities=filters.get("person_seniorities", None),
        q_organization_search_list_id=filters.get("q_organization_search_list_id", None),
        q_organization_keyword_tags=filters.get("q_organization_keyword_tags", None),
        organization_department_or_subdepartment_counts=filters.get("organization_department_or_subdepartment_counts", None),
        is_prefilter=True
    )

    return {
        "response": friendly_acknowledgment,
        "data": json.loads(jsonify(data).get_data(as_text=True)),
        "makers": segment_name,
        "industry": segment_description,
        "pain_point": segment_value_proposition
    }
