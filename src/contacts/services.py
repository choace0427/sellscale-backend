import json
import yaml
import os
from typing import Optional
from app import db
import requests
from src.client.models import ClientArchetype, ClientSDR
from src.contacts.models import SavedApolloQuery

from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.prospecting.controllers import add_prospect_from_csv_payload
from src.prospecting.models import ProspectUploadSource
from src.utils.abstract.attr_utils import deep_get
from datetime import datetime

import concurrent.futures

from src.utils.hasher import generate_uuid

# APOLLO CREDENTIALS (SESSION and XCSRF are reverse engineered tokens, may require manual refreshing periodically)
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY")
APOLLO_SESSION_COOKIE = os.environ.get("APOLLO_SESSION_COOKIE")
APOLLO_XCSRF_TOKEN = os.environ.get("APOLLO_XCSRF_TOKEN")

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

    return {
        "breadcrumbs": breadcrumbs,
        "partial_results_only": partial_results_only,
        "disable_eu_prospecting": disable_eu_prospecting,
        "partial_results_limit": partial_results_limit,
        "pagination": pagination,
        "contacts": contacts,
        "people": people,
        "saved_query_id": saved_query_id,
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
    # Set the headers
    headers = {
        "x-csrf-token": APOLLO_XCSRF_TOKEN,
        "cookie": APOLLO_SESSION_COOKIE,
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
            company_id = populate_company_from_apollo_result(result)
            print("Updated Company ID", company_id)

    return results


def apollo_get_pre_filters(
    client_sdr_id: int,
    persona_id: Optional[int] = None,
    segment_id: Optional[int] = None,
):

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
    or (
      saved_apollo_query.is_prefilter
    )
  )
order by saved_apollo_query.created_at desc
limit 1
    """

    d_results = []
    results = db.engine.execute(query).fetchall()
    for row in results:
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

    data = yaml.safe_load(completion)

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

        data = yaml.safe_load(completion)

        overall_filters[filter_type] = data["data"]

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
