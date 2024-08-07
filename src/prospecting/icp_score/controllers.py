from src.client.models import ClientArchetype, ClientSDR, Client
from src.prospecting.models import Prospect
from src.authentication.decorators import require_user
from app import db

from flask import Blueprint, jsonify, request
from src.prospecting.icp_score.services import (
    generate_new_icp_filters,
    update_icp_filters,
    update_icp_scoring_ruleset,
    move_selected_prospects_to_unassigned,
    apply_icp_scoring_ruleset_filters_task,
    clear_icp_ruleset,
    set_icp_scores_to_predicted_values,
    update_icp_titles_from_sales_nav_url,
    score_ai_filters
)
from src.utils.request_helpers import get_request_parameter
from src.prospecting.icp_score.models import ICPScoringJobQueue, ICPScoringRuleset

ICP_SCORING_BLUEPRINT = Blueprint("icp_scoring", __name__)


@ICP_SCORING_BLUEPRINT.route("/runs", methods=["GET"])
@require_user
def get_runs(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )

    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    if not client_archetype or client_archetype.client_sdr_id != client_sdr_id:
        return {"status": "error", "message": "Unauthorized"}, 401

    jobs: list[ICPScoringJobQueue] = (
        ICPScoringJobQueue.query.filter_by(client_archetype_id=client_archetype_id)
        .order_by(ICPScoringJobQueue.id.desc())
        .all()
    )

    jobs_dicts = [job.to_dict() for job in jobs]

    return {"status": "success", "data": {"icp_runs": jobs_dicts}}, 200


@ICP_SCORING_BLUEPRINT.route("/runs", methods=["POST"])
@require_user
def post_manual_trigger_rerun(client_sdr_id: int):
    icp_scoring_job_queue_id = get_request_parameter(
        "icp_scoring_job_queue_id", request, json=True, required=True
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=False
    )

    apply_icp_scoring_ruleset_filters_task(
        client_archetype_id=client_archetype_id,
        icp_scoring_job_queue_id=icp_scoring_job_queue_id,
        prospect_ids=prospect_ids,
        manual_trigger=True,
    )

    return {"status": "success"}, 200


@ICP_SCORING_BLUEPRINT.route("/get_ruleset", methods=["GET"])
@require_user
def get_ruleset(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=False, required=True
    )
    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    if not client_sdr or client_sdr.id != client_archetype.client_sdr_id:
        return "Unauthorized", 401

    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()

    if not icp_scoring_ruleset:
        return "No ICP Scoring Ruleset found", 404

    return jsonify(icp_scoring_ruleset.to_dict()), 200


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
    included_individual_education_keywords = get_request_parameter(
        "included_individual_education_keywords", request, json=True, required=False
    )
    excluded_individual_education_keywords = get_request_parameter(
        "excluded_individual_education_keywords", request, json=True, required=False
    )
    included_individual_seniority_keywords = get_request_parameter(
        "included_individual_seniority_keywords", request, json=True, required=False
    )
    excluded_individual_seniority_keywords = get_request_parameter(
        "excluded_individual_seniority_keywords", request, json=True, required=False
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
        included_individual_education_keywords=included_individual_education_keywords,
        excluded_individual_education_keywords=excluded_individual_education_keywords,
        included_individual_seniority_keywords=included_individual_seniority_keywords,
        excluded_individual_seniority_keywords=excluded_individual_seniority_keywords,
    )

    if updated_score:
        return "OK", 200

    return "Failed to update ICP Scoring Ruleset", 500


@ICP_SCORING_BLUEPRINT.route("/run_on_prospects", methods=["POST"])
@require_user
def run_on_prospects(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=False
    )
    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    if not client_archetype or client_archetype.client_sdr_id != client_sdr_id:
        return "Unauthorized", 401

    success = apply_icp_scoring_ruleset_filters_task(
        client_archetype_id=client_archetype_id,
        prospect_ids=prospect_ids,
        manual_trigger=True,
    )

    if success:
        return "OK", 200
    return "Failed to apply ICP Scoring Ruleset", 500


@ICP_SCORING_BLUEPRINT.route("/move_selected_prospects_to_unassigned", methods=["POST"])
@require_user
def post_move_selected_prospects_to_unassigned(client_sdr_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()

    not_client_sdrs_prospects: Prospect = Prospect.query.filter(
        Prospect.id.in_(prospect_ids), Prospect.client_id != client_sdr.client_id
    ).all()
    if not_client_sdrs_prospects:
        return "Unauthorized - selected prospects do not belong to this user.", 401

    move_selected_prospects_to_unassigned(prospect_ids=prospect_ids)

    return "OK", 200


@ICP_SCORING_BLUEPRINT.route("/set_icp_scores_to_predicted_values", methods=["POST"])
@require_user
def post_set_icp_scores_to_predicted_values(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()

    if not client_archetype or client_archetype.client_sdr_id != client_sdr_id:
        return "Unauthorized", 401

    success = set_icp_scores_to_predicted_values(
        client_archetype_id=client_archetype_id
    )

    if success:
        return "OK", 200
    return "Failed to set ICP scores to predicted values", 500


@ICP_SCORING_BLUEPRINT.route("/clear_icp_ruleset", methods=["POST"])
@require_user
def post_clear_icp_ruleset(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )
    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()

    if not client_archetype or client_archetype.client_sdr_id != client_sdr_id:
        return "Unauthorized", 401

    success = clear_icp_ruleset(client_archetype_id=client_archetype_id)

    if success:
        return "OK", 200
    return "Failed to clear ICP ruleset", 500


@ICP_SCORING_BLUEPRINT.route("/generate_new_icp_filters", methods=["POST"])
@require_user
def post_generate_new_icp_filters(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )

    message = get_request_parameter("message", request, json=True, required=True)

    result = generate_new_icp_filters(
        client_archetype_id=client_archetype_id, message=message
    )

    return jsonify({"message": "Success", "data": result}), 200


@ICP_SCORING_BLUEPRINT.route("/update_icp_filters", methods=["POST"])
@require_user
def post_update_icp_filters(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )

    filters = get_request_parameter("filters", request, json=True, required=True)

    result = update_icp_filters(
        client_archetype_id=client_archetype_id, filters=filters
    )

    return jsonify({"message": "Success", "data": result}), 200


@ICP_SCORING_BLUEPRINT.route("/update_icp_filters_from_sales_nav_url", methods=["POST"])
@require_user
def update_icp_filters_from_sales_nav_url(client_sdr_id: int):
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True
    )

    sales_nav_url = get_request_parameter(
        "sales_nav_url", request, json=True, required=True
    )

    success = update_icp_titles_from_sales_nav_url(
        client_archetype_id=client_archetype_id, sales_nav_url=sales_nav_url
    )

    return jsonify({"message": "Success", "data": success}), 200
