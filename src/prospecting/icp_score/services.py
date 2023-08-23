from src.prospecting.icp_score.models import ICPScoringRuleset
from app import db


def update_icp_scoring_ruleset(
    client_archetype_id: int,
    included_individual_title_keywords: list,
    excluded_individual_title_keywords: list,
    included_individual_industry_keywords: list,
    excluded_individual_industry_keywords: list,
    individual_years_of_experience_start: int,
    individual_years_of_experience_end: int,
    included_individual_skills_keywords: list,
    excluded_individual_skills_keywords: list,
    included_individual_locations_keywords: list,
    excluded_individual_locations_keywords: list,
    included_individual_generalized_keywords: list,
    excluded_individual_generalized_keywords: list,
    included_company_name_keywords: list,
    excluded_company_name_keywords: list,
    included_company_locations_keywords: list,
    excluded_company_locations_keywords: list,
    company_size_start: int,
    company_size_end: int,
    included_company_industries_keywords: list,
    excluded_company_industries_keywords: list,
    included_company_generalized_keywords: list,
    excluded_company_generalized_keywords: list,
):
    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()
    if not icp_scoring_ruleset:
        empty_icp_scoring_ruleset = ICPScoringRuleset(
            client_archetype_id=client_archetype_id,
        )
        db.session.add(empty_icp_scoring_ruleset)
        db.session.commit()

    icp_scoring_ruleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()

    icp_scoring_ruleset.included_individual_title_keywords = (
        included_individual_title_keywords
    )
    icp_scoring_ruleset.excluded_individual_title_keywords = (
        excluded_individual_title_keywords
    )
    icp_scoring_ruleset.included_individual_industry_keywords = (
        included_individual_industry_keywords
    )
    icp_scoring_ruleset.excluded_individual_industry_keywords = (
        excluded_individual_industry_keywords
    )
    icp_scoring_ruleset.individual_years_of_experience_start = (
        individual_years_of_experience_start
    )
    icp_scoring_ruleset.individual_years_of_experience_end = (
        individual_years_of_experience_end
    )
    icp_scoring_ruleset.included_individual_skills_keywords = (
        included_individual_skills_keywords
    )
    icp_scoring_ruleset.excluded_individual_skills_keywords = (
        excluded_individual_skills_keywords
    )
    icp_scoring_ruleset.included_individual_locations_keywords = (
        included_individual_locations_keywords
    )
    icp_scoring_ruleset.excluded_individual_locations_keywords = (
        excluded_individual_locations_keywords
    )
    icp_scoring_ruleset.included_individual_generalized_keywords = (
        included_individual_generalized_keywords
    )
    icp_scoring_ruleset.excluded_individual_generalized_keywords = (
        excluded_individual_generalized_keywords
    )
    icp_scoring_ruleset.included_company_name_keywords = included_company_name_keywords
    icp_scoring_ruleset.excluded_company_name_keywords = excluded_company_name_keywords
    icp_scoring_ruleset.included_company_locations_keywords = (
        included_company_locations_keywords
    )
    icp_scoring_ruleset.excluded_company_locations_keywords = (
        excluded_company_locations_keywords
    )
    icp_scoring_ruleset.company_size_start = company_size_start
    icp_scoring_ruleset.company_size_end = company_size_end
    icp_scoring_ruleset.included_company_industries_keywords = (
        included_company_industries_keywords
    )
    icp_scoring_ruleset.excluded_company_industries_keywords = (
        excluded_company_industries_keywords
    )
    icp_scoring_ruleset.included_company_generalized_keywords = (
        included_company_generalized_keywords
    )
    icp_scoring_ruleset.excluded_company_generalized_keywords = (
        excluded_company_generalized_keywords
    )

    db.session.add(icp_scoring_ruleset)
    db.session.commit()

    return icp_scoring_ruleset
