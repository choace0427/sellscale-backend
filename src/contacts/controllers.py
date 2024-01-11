from flask import Blueprint, jsonify, request

from src.contacts.services import get_contacts
from src.utils.request_helpers import get_request_parameter


CONTACTS_BLUEPRINT = Blueprint("contacts", __name__)


@CONTACTS_BLUEPRINT.route("/search", methods=["POST"])
def index():
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

    data = get_contacts(
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
    )

    return jsonify(data)
