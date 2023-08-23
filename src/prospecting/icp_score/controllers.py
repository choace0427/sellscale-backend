from src.client.models import ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.authentication.decorators import require_user
from app import db

from flask import Blueprint, jsonify, request
from src.prospecting.icp_score.services import update_icp_scoring_ruleset
from src.utils.request_helpers import get_request_parameter

ICP_SCORING_BLUEPRINT = Blueprint("icp_scoring", __name__)


@ICP_SCORING_BLUEPRINT.route("/update_ruleset", methods=["POST"])
@require_user
def update_ruleset(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    if not client_sdr or client_sdr.id != client_archetype.client_sdr_id:
        return "Unauthorized", 401

    included_individual_title_keywords = get_request_parameter(
        "included_individual_title_keywords", request, json=True, required=False
    )
    excluded_individual_title_keywords = get_request_parameter(
        "excluded_individual_title_keywords", request, json=True, required=False
    )
    included_individual_industry_keywords = get_request_parameter(
        "included_individual_industry_keywords", request, json=True, required=False
    )
    excluded_individual_industry_keywords = get_request_parameter(
        "excluded_individual_industry_keywords", request, json=True, required=False
    )
    individual_years_of_experience_start = get_request_parameter(
        "individual_years_of_experience_start", request, json=True, required=False
    )
    individual_years_of_experience_end = get_request_parameter(
        "individual_years_of_experience_end", request, json=True, required=False
    )
    included_individual_skills_keywords = get_request_parameter(
        "included_individual_skills_keywords", request, json=True, required=False
    )
    excluded_individual_skills_keywords = get_request_parameter(
        "excluded_individual_skills_keywords", request, json=True, required=False
    )
    included_individual_locations_keywords = get_request_parameter(
        "included_individual_locations_keywords", request, json=True, required=False
    )
    excluded_individual_locations_keywords = get_request_parameter(
        "excluded_individual_locations_keywords", request, json=True, required=False
    )
    included_individual_generalized_keywords = get_request_parameter(
        "included_individual_generalized_keywords", request, json=True, required=False
    )
    excluded_individual_generalized_keywords = get_request_parameter(
        "excluded_individual_generalized_keywords", request, json=True, required=False
    )
    included_company_name_keywords = get_request_parameter(
        "included_company_name_keywords", request, json=True, required=False
    )
    excluded_company_name_keywords = get_request_parameter(
        "excluded_company_name_keywords", request, json=True, required=False
    )
    included_company_locations_keywords = get_request_parameter(
        "included_company_locations_keywords", request, json=True, required=False
    )
    excluded_company_locations_keywords = get_request_parameter(
        "excluded_company_locations_keywords", request, json=True, required=False
    )
    company_size_start = get_request_parameter(
        "company_size_start", request, json=True, required=False
    )
    company_size_end = get_request_parameter(
        "company_size_end", request, json=True, required=False
    )
    included_company_industries_keywords = get_request_parameter(
        "included_company_industries_keywords", request, json=True, required=False
    )
    excluded_company_industries_keywords = get_request_parameter(
        "excluded_company_industries_keywords", request, json=True, required=False
    )
    included_company_generalized_keywords = get_request_parameter(
        "included_company_generalized_keywords", request, json=True, required=False
    )
    excluded_company_generalized_keywords = get_request_parameter(
        "excluded_company_generalized_keywords", request, json=True, required=False
    )

    updated_score = update_icp_scoring_ruleset(
        client_archetype_id=client_archetype_id,
        included_individual_title_keywords=included_individual_title_keywords,
        excluded_individual_title_keywords=excluded_individual_title_keywords,
        included_individual_industry_keywords=included_individual_industry_keywords,
        excluded_individual_industry_keywords=excluded_individual_industry_keywords,
        individual_years_of_experience_start=individual_years_of_experience_start,
        individual_years_of_experience_end=individual_years_of_experience_end,
        included_individual_skills_keywords=included_individual_skills_keywords,
        excluded_individual_skills_keywords=excluded_individual_skills_keywords,
        included_individual_locations_keywords=included_individual_locations_keywords,
        excluded_individual_locations_keywords=excluded_individual_locations_keywords,
        included_individual_generalized_keywords=included_individual_generalized_keywords,
        excluded_individual_generalized_keywords=excluded_individual_generalized_keywords,
        included_company_name_keywords=included_company_name_keywords,
        excluded_company_name_keywords=excluded_company_name_keywords,
        included_company_locations_keywords=included_company_locations_keywords,
        excluded_company_locations_keywords=excluded_company_locations_keywords,
        company_size_start=company_size_start,
        company_size_end=company_size_end,
        included_company_industries_keywords=included_company_industries_keywords,
        excluded_company_industries_keywords=excluded_company_industries_keywords,
        included_company_generalized_keywords=included_company_generalized_keywords,
        excluded_company_generalized_keywords=excluded_company_generalized_keywords,
    )

    if updated_score:
        return "OK", 200

    return "Failed to update ICP Scoring Ruleset", 500