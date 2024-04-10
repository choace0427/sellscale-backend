from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user

from src.contacts.services import (
    apollo_get_contacts,
    apollo_get_organizations_from_company_names,
    get_company_name_using_urllib,
    get_territories,
    predict_filters_needed,
)
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.utils.request_helpers import get_request_parameter


CONTACTS_BLUEPRINT = Blueprint("contacts", __name__)


@CONTACTS_BLUEPRINT.route("/search", methods=["POST"])
@require_user
def index(client_sdr_id: int):
    num_contacts = get_request_parameter(
        "num_contacts", request, json=True, required=False, default_value=100
    )
    person_titles = get_request_parameter(
        "person_titles", request, json=True, required=False, default_value=[]
    )
    person_not_titles = get_request_parameter(
        "person_not_titles", request, json=True, required=False, default_value=[]
    )
    q_person_title = get_request_parameter(
        "q_person_title", request, json=True, required=False, default_value=""
    )
    q_person_name = get_request_parameter(
        "q_person_name", request, json=True, required=False, default_value=""
    )
    organization_industry_tag_ids = get_request_parameter(
        "organization_industry_tag_ids",
        request,
        json=True,
        required=False,
        default_value=[],
    )
    organization_num_employees_ranges = get_request_parameter(
        "organization_num_employees_ranges",
        request,
        json=True,
        required=False,
        default_value=None,
    )
    person_locations = get_request_parameter(
        "person_locations", request, json=True, required=False, default_value=[]
    )
    organization_ids = get_request_parameter(
        "organization_ids", request, json=True, required=False, default_value=None
    )
    revenue_range = get_request_parameter(
        "revenue_range",
        request,
        json=True,
        required=False,
        default_value={"min": None, "max": None},
    )
    organization_latest_funding_stage_cd = get_request_parameter(
        "organization_latest_funding_stage_cd",
        request,
        json=True,
        required=False,
        default_value=[],
    )
    currently_using_any_of_technology_uids = get_request_parameter(
        "currently_using_any_of_technology_uids",
        request,
        json=True,
        required=False,
        default_value=[],
    )
    event_categories = get_request_parameter(
        "event_categories", request, json=True, required=False, default_value=None
    )
    published_at_date_range = get_request_parameter(
        "published_at_date_range",
        request,
        json=True,
        required=False,
        default_value=None,
    )
    person_seniorities = get_request_parameter(
        "person_seniorities", request, json=True, required=False, default_value=None
    )
    q_organization_search_list_id = get_request_parameter(
        "q_organization_search_list_id",
        request,
        json=True,
        required=False,
        default_value=None,
    )
    q_organization_keyword_tags = get_request_parameter(
        "q_organization_keyword_tags",
        request,
        json=True,
        required=False,
        default_value=None,
    )
    organization_department_or_subdepartment_counts = get_request_parameter(
        "organization_department_or_subdepartment_counts",
        request,
        json=True,
        required=False,
        default_value=None,
    )

    is_prefilter = get_request_parameter(
        "is_prefilter",
        request,
        json=True,
        required=False,
        default_value=None,
    )

    data = apollo_get_contacts(
        client_sdr_id=client_sdr_id,
        num_contacts=num_contacts,
        person_titles=person_titles,
        person_not_titles=person_not_titles,
        q_person_title=q_person_title,
        q_person_name=q_person_name,
        organization_industry_tag_ids=organization_industry_tag_ids,
        organization_num_employees_ranges=organization_num_employees_ranges,
        person_locations=person_locations,
        organization_ids=organization_ids,
        revenue_range=revenue_range,
        organization_latest_funding_stage_cd=organization_latest_funding_stage_cd,
        currently_using_any_of_technology_uids=currently_using_any_of_technology_uids,
        event_categories=event_categories,
        published_at_date_range=published_at_date_range,
        person_seniorities=person_seniorities,
        q_organization_search_list_id=q_organization_search_list_id,
        organization_department_or_subdepartment_counts=organization_department_or_subdepartment_counts,
        is_prefilter=is_prefilter,
        q_organization_keyword_tags=q_organization_keyword_tags,
    )

    predicted_segment_name = ""
    try:
        filters = ""
        for item in data.get("breadcrumbs", []):
            filters += "{}: {}\n".format(item.get("label"), item.get("display_name"))

        predicted_segment_name = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": "Instruction: Using the following filters, summarize the contacts in a short, 5-6 word phrease.\n\nFilters:\n{}\nSummary:".format(
                        filters
                    ),
                }
            ]
        )
    except Exception as e:
        print(e)

    data["predicted_segment_name"] = predicted_segment_name

    return jsonify(data)


@CONTACTS_BLUEPRINT.route("/company_search", methods=["POST"])
@require_user
def get_company(client_sdr_id: int):
    company_names = get_request_parameter(
        "company_names", request, json=True, required=False, default_value=None
    )
    company_urls = get_request_parameter(
        "company_urls", request, json=True, required=False, default_value=None
    )
    if not company_names and not company_urls:
        return jsonify(
            {
                "status": "error",
                "message": "Company names or urls must be provided.",
            }
        )

    # Get organizations from company names
    data: list = []
    if company_names:
        orgs = apollo_get_organizations_from_company_names(
            client_sdr_id=client_sdr_id,
            company_names=company_names,
        )
        data.extend(orgs)

    if company_urls:
        converted_names = get_company_name_using_urllib(
            urls=company_urls,
        )
        orgs = apollo_get_organizations_from_company_names(
            client_sdr_id=client_sdr_id,
            company_names=converted_names,
        )
        data.extend(orgs)

    # Deduplicate
    data = [dict(t) for t in {tuple(d.items()) for d in data}]

    return jsonify(
        {
            "status": "success",
            "data": data,
        }
    )


@CONTACTS_BLUEPRINT.route("/predict_contact_filters", methods=["POST"])
@require_user
def predict_contact_filters(client_sdr_id: int):
    query = get_request_parameter("query", request, json=True, required=True)

    filters = predict_filters_needed(
        query=query,
    )

    return jsonify(filters)


@CONTACTS_BLUEPRINT.route("/territories", methods=["GET"])
@require_user
def get_territories_request(client_sdr_id: int):
    territories = get_territories(client_sdr_id=client_sdr_id)

    return jsonify({"territories": territories})
