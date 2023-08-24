import datetime
from src.prospecting.icp_score.models import ICPScoringRuleset
from app import db
from src.prospecting.models import Prospect
from model_import import ResearchPayload
from src.utils.abstract.attr_utils import deep_get
from sqlalchemy.sql.expression import func


class EnrichedProspectCompany:
    prospect_title: str
    prospect_linkedin_url: str
    prospect_bio: str
    prospect_location: str
    prospect_industry: str
    prospect_skills: list
    prospect_positions: list
    prospect_years_of_experience: int
    prospect_dump: str

    company_name: str
    company_location: str
    company_employee_count: int
    company_description: str
    company_tagline: str
    company_dump: str


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


def count_num_icp_attributes(client_archetype_id: int):
    icp_scoring_ruleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()
    if not icp_scoring_ruleset:
        return 0

    count = 0
    if (
        icp_scoring_ruleset.included_individual_title_keywords
        or icp_scoring_ruleset.excluded_individual_title_keywords
    ):
        count += 1
    if (
        icp_scoring_ruleset.included_individual_industry_keywords
        or icp_scoring_ruleset.excluded_individual_industry_keywords
    ):
        count += 1
    if (
        icp_scoring_ruleset.individual_years_of_experience_start
        or icp_scoring_ruleset.individual_years_of_experience_end
    ):
        count += 1
    if (
        icp_scoring_ruleset.included_individual_skills_keywords
        or icp_scoring_ruleset.excluded_individual_skills_keywords
    ):
        count += 1
    if (
        icp_scoring_ruleset.included_individual_locations_keywords
        or icp_scoring_ruleset.excluded_individual_locations_keywords
    ):
        count += 1
    if (
        icp_scoring_ruleset.included_individual_generalized_keywords
        or icp_scoring_ruleset.excluded_individual_generalized_keywords
    ):
        count += 1
    if (
        icp_scoring_ruleset.included_company_name_keywords
        or icp_scoring_ruleset.excluded_company_name_keywords
    ):
        count += 1
    if (
        icp_scoring_ruleset.included_company_locations_keywords
        or icp_scoring_ruleset.excluded_company_locations_keywords
    ):
        count += 1
    if icp_scoring_ruleset.company_size_start or icp_scoring_ruleset.company_size_end:
        count += 1
    if (
        icp_scoring_ruleset.included_company_industries_keywords
        or icp_scoring_ruleset.excluded_company_industries_keywords
    ):
        count += 1
    if (
        icp_scoring_ruleset.included_company_generalized_keywords
        or icp_scoring_ruleset.excluded_company_generalized_keywords
    ):
        count += 1

    return count


def get_raw_enriched_prospect_companies_list(client_archetype_id: int):
    entries = (
        db.session.query(
            Prospect.id.label("prospect_id"),
            func.array_agg(ResearchPayload.payload.label("research")),
            Prospect.title.label("prospect_title"),
            Prospect.industry.label("prospect_industry"),
            Prospect.linkedin_bio.label("prospect_bio"),
            Prospect.company.label("company_name"),
            Prospect.employee_count.label("employee_count"),
            Prospect.linkedin_url.label("linkedin_url"),
        )
        .outerjoin(ResearchPayload, Prospect.id == ResearchPayload.prospect_id)
        .filter(Prospect.archetype_id == client_archetype_id)
        .group_by(
            Prospect.id,
            Prospect.title,
            Prospect.industry,
            Prospect.linkedin_bio,
            Prospect.company,
            Prospect.employee_count,
            Prospect.linkedin_url,
        )
        .all()
    )

    processed = {}
    for entry in entries:
        prospect_id = entry[0]
        processed[prospect_id] = EnrichedProspectCompany()

        title = entry[2]
        industry = entry[3]
        bio = entry[4]
        company_name = entry[5]
        employee_count = entry[6]
        linkedin_url = entry[7]

        data = entry[1][0] if len(entry[1]) > 0 else {}

        processed[prospect_id].prospect_title = title
        processed[prospect_id].prospect_linkedin_url = linkedin_url
        processed[prospect_id].prospect_bio = bio
        processed[prospect_id].prospect_location = str(
            deep_get(data, "personal.location")
        )
        processed[prospect_id].prospect_industry = industry
        processed[prospect_id].prospect_skills = deep_get(data, "personal.skills")
        processed[prospect_id].prospect_positions = deep_get(
            data, "personal.profile_positions"
        )
        processed[prospect_id].prospect_years_of_experience = (
            datetime.datetime.now().year
            - deep_get(processed[prospect_id].prospect_positions[-1], "date.start.year")
            if processed[prospect_id].prospect_positions
            else None
        )
        processed[prospect_id].prospect_dump = str(deep_get(data, "personal"))

        processed[prospect_id].company_name = company_name
        processed[prospect_id].company_location = (
            (
                deep_get(data, "company.details.locations.headquarter.city")
                if deep_get(data, "company.details.locations.headquarter.city")
                else ""
            )
            + ", "
            + (
                deep_get(data, "company.details.locations.headquarter.geographic_area")
                if deep_get(
                    data, "company.details.locations.headquarter.geographic_area"
                )
                else ""
            )
            + ", "
            + (
                deep_get(data, "company.details.locations.headquarter.country")
                if deep_get(data, "company.details.locations.headquarter.country")
                else ""
            )
        )
        processed[prospect_id].company_employee_count = deep_get(
            data, "company.details.staff.total"
        ) or (employee_count.split("-")[0] if employee_count else None)
        processed[prospect_id].company_description = deep_get(
            data, "company.details.description"
        )
        processed[prospect_id].company_tagline = deep_get(
            data, "company.details.tagline"
        )
        processed[prospect_id].company_dump = str(deep_get(data, "company"))

    return processed


def score_one_prospect(
    enriched_prospect_company: EnrichedProspectCompany,
    icp_scoring_ruleset: ICPScoringRuleset,
):
    num_attributes = count_num_icp_attributes(icp_scoring_ruleset.client_archetype_id)
    score = 0
    if (
        icp_scoring_ruleset.included_individual_title_keywords
        and enriched_prospect_company.prospect_title
        and any(
            keyword in enriched_prospect_company.prospect_title
            for keyword in icp_scoring_ruleset.included_individual_title_keywords
        )
    ):
        score += 1
    if (
        icp_scoring_ruleset.excluded_individual_title_keywords
        and enriched_prospect_company.prospect_title
        and any(
            keyword in enriched_prospect_company.prospect_title
            for keyword in icp_scoring_ruleset.excluded_individual_title_keywords
        )
    ):
        score -= num_attributes
    return (enriched_prospect_company, score)


def apply_icp_scoring_ruleset_filters(client_archetype_id: int):
    num_attributes = count_num_icp_attributes(client_archetype_id)
    raw_enriched_prospect_companies_list = get_raw_enriched_prospect_companies_list(
        client_archetype_id
    )
    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()

    for (
        prospect_id,
        enriched_prospect_company,
    ) in raw_enriched_prospect_companies_list.items():
        print(prospect_id)
        print(enriched_prospect_company)
        print(score_one_prospect(enriched_prospect_company, icp_scoring_ruleset))
