import base64
import json

from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user

from src.contacts.services import (
    apollo_get_contacts,
    apollo_get_organizations,
    apollo_get_pre_filters,
    get_territories,
    handle_chat_icp,
    predict_filters_needed,
    get_apollo_queries_under_sdr,
)
from src.company.services import find_company, find_company_name_from_url
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.utils.request_helpers import get_request_parameter
from sqlalchemy import or_
from src.company.models import Company, CompanyRelation
from src.vision.services import attempt_chat_completion_with_vision_base64

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
    company_prompt = get_request_parameter(
        "company_prompt", request, json=True, required=False, default_value=None
    )

    if not company_names and not company_urls and not company_prompt:
        return jsonify(
            {
                "status": "error",
                "message": "Company names or urls must be provided.",
            }
        )

    # Get the organizations
    data = apollo_get_organizations(
        client_sdr_id=client_sdr_id,
        company_names=company_names,
        company_urls=company_urls,
        company_prompt=company_prompt,
    )

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


@CONTACTS_BLUEPRINT.route("/image_company_extract", methods=["POST"])
@require_user
def post_image_company_extract(client_sdr_id: int):
    files = request.files.getlist('files')

    file_name_to_base64 = {}
    for file in files:
        file_name_to_base64[file.filename] = base64.b64encode(file.read()).decode('utf-8')

    file_name_to_companies = []

    message = """
    Instructions: You will be given an image which contains images of company logos, or text of companies.
    You are to extract them, and generate a list of companies names without descriptions.
    You will output the list of company names in a json format, with the key being "companies", and the value being a list of company names.
    """

    for file_name in file_name_to_base64.keys():
        base_64 = file_name_to_base64[file_name]

        success, response = attempt_chat_completion_with_vision_base64(
            message=message,
            base_64_image=base_64,
        )

        if success:
            cleaned_response = response.replace('```', '').replace('json', '').replace('\n', '')
            response_json = json.loads(cleaned_response)

            companies = response_json.get('companies', [])

            for company in companies:
                file_name_to_companies.append((file_name, company))

    return jsonify({"data": file_name_to_companies, "status": "success"})


@CONTACTS_BLUEPRINT.route("/get_pre_filters", methods=["GET"])
@require_user
def get_apollo_get_pre_filters(client_sdr_id: int):
    persona_id = get_request_parameter(
        "persona_id", request, json=False, required=False
    )
    segment_id = get_request_parameter(
        "segment_id", request, json=False, required=False
    )

    saved_query_id = get_request_parameter(
        "saved_query_id", request, json=False, required=False
    )

    data = apollo_get_pre_filters(
        client_sdr_id=client_sdr_id,
        persona_id=persona_id,
        segment_id=segment_id,
        saved_query_id=saved_query_id,
    )

    return jsonify(
        {
            "status": "success",
            "data": data,
        }
    )

@CONTACTS_BLUEPRINT.route("/all_prefilters", methods=["GET"])
@require_user
def get_apollo_queries(client_sdr_id: int):
    queries = get_apollo_queries_under_sdr(client_sdr_id)
    return jsonify({
        "status": "success",
        "data": queries,
    })

@CONTACTS_BLUEPRINT.route("/magic_apollo_search", methods=["POST"])
@require_user
def query_then_search(client_sdr_id: int):
    query = get_request_parameter("query", request, json=True, required=True)
    filters = predict_filters_needed(query, use_apollo_filters=True)

    print('filters are', filters)

    data = apollo_get_contacts(
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
        is_prefilter=filters.get("is_prefilter", None),
    )

    return jsonify(data)

@CONTACTS_BLUEPRINT.route("/chat-icp", methods=["POST"])
@require_user
def post_chat_icp(client_sdr_id: int):
    """
    Handle chat ICP requests
    """
    prompt = get_request_parameter(
        "prompt", request, json=True, required=True, parameter_type=str
    )
    chat_content = get_request_parameter(
        "chatContent", request, json=True, required=True, parameter_type=list
    )

    current_csv = get_request_parameter(
        "currentCSV", request, json=True, required=False, parameter_type=str
    )
    #if current csv is not provided, it will be set to ''
    if not current_csv:
        current_csv = ''

    # Assuming the function handle_chat_icp is defined in src/ml/services.py
    response = handle_chat_icp(client_sdr_id=client_sdr_id,prompt=prompt, chat_content=chat_content)

    if not response:
        return jsonify({"message": "Error handling chat ICP"}), 400

    return jsonify(response), 200
