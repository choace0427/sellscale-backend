import datetime
from multiprocessing import process

from flask import app
from src.client.models import ClientArchetype
from src.prospecting.icp_score.models import ICPScoringRuleset
from app import db, app, celery
from src.prospecting.models import Prospect
from model_import import ResearchPayload
from src.utils.abstract.attr_utils import deep_get
from sqlalchemy.sql.expression import func
from tqdm import tqdm

import queue
import concurrent.futures


class EnrichedProspectCompany:
    prospect_id: int
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
    """
    Count the number of ICP attributes.
    """
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


def get_raw_enriched_prospect_companies_list(
    client_archetype_id: int, prospect_ids: list[int]
):
    """
    Get the raw enriched prospect companies list.
    """
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
    )

    if prospect_ids:
        entries = entries.filter(Prospect.id.in_(prospect_ids))

    entries = entries.all()

    processed = {}
    for entry in entries:
        prospect_id = entry[0]
        processed[prospect_id] = EnrichedProspectCompany()

        processed[prospect_id].prospect_id = prospect_id

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
            data, "personal.position_groups.0.profile_positions"
        )
        processed[prospect_id].prospect_years_of_experience = (
            datetime.datetime.now().year
            - deep_get(processed[prospect_id].prospect_positions[-1], "date.start.year")
            if processed[prospect_id].prospect_positions
            else None
        )

        position_title = deep_get(
            data, "personal.position_groups.0.profile_positions.0.title"
        )
        position_description = deep_get(
            data, "personal.position_groups.0.profile_positions.0.description"
        )
        personal_bio = deep_get(data, "personal.bio")
        processed[prospect_id].prospect_dump = (
            str(position_title)
            + " "
            + str(position_description)
            + " "
            + str(personal_bio)
        )

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
        if deep_get(data, "company.details.locations.headquarter.country") == "US":
            processed[prospect_id].company_location += " United States"
        elif deep_get(data, "company.details.locations.headquarter.country") == "CA":
            processed[prospect_id].company_location += " Canada"
        processed[prospect_id].company_employee_count = deep_get(
            data, "company.details.staff.total"
        ) or (employee_count.split("-")[0] if employee_count else None)
        processed[prospect_id].company_description = deep_get(
            data, "company.details.description"
        )
        processed[prospect_id].company_tagline = deep_get(
            data, "company.details.tagline"
        )

        processed[prospect_id].company_dump = str(
            deep_get(data, "company.details.description")
        )

    return processed


def score_one_prospect(
    enriched_prospect_company: EnrichedProspectCompany,
    icp_scoring_ruleset: ICPScoringRuleset,
    queue: queue.Queue,
):
    """
    Score one prospect based on the ICP scoring ruleset.
    """
    print("Scoring prospect: " + str(enriched_prospect_company.prospect_id))
    with app.app_context():
        num_attributes = count_num_icp_attributes(
            icp_scoring_ruleset.client_archetype_id
        )
        score = 0
        reasoning = ""

        # Prospect Title
        if (
            icp_scoring_ruleset.excluded_individual_title_keywords
            and enriched_prospect_company.prospect_title
            and any(
                keyword.lower() in enriched_prospect_company.prospect_title.lower()
                for keyword in icp_scoring_ruleset.excluded_individual_title_keywords
            )
        ):
            score -= num_attributes
            # find the invalid title
            invalid_title = ""
            for keyword in icp_scoring_ruleset.excluded_individual_title_keywords:
                if keyword.lower() in enriched_prospect_company.prospect_title.lower():
                    invalid_title = keyword
                    break
            reasoning += "(❌ prospect title: " + invalid_title + ") "
        elif (
            icp_scoring_ruleset.included_individual_title_keywords
            and enriched_prospect_company.prospect_title
            and any(
                keyword.lower() in enriched_prospect_company.prospect_title.lower()
                for keyword in icp_scoring_ruleset.included_individual_title_keywords
            )
        ):
            score += 1
            valid_title = ""
            for keyword in icp_scoring_ruleset.included_individual_title_keywords:
                if keyword.lower() in enriched_prospect_company.prospect_title.lower():
                    valid_title = keyword
                    break
            reasoning += "(✅ prospect title: " + valid_title + ") "

        # Prospect Industry
        if (
            icp_scoring_ruleset.excluded_individual_industry_keywords
            and enriched_prospect_company.prospect_industry
            and any(
                keyword.lower() in enriched_prospect_company.prospect_industry.lower()
                for keyword in icp_scoring_ruleset.excluded_individual_industry_keywords
            )
        ):
            score -= num_attributes
            invalid_industry = ""
            for keyword in icp_scoring_ruleset.excluded_individual_industry_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.prospect_industry.lower()
                ):
                    invalid_industry = keyword
                    break
            reasoning += "(❌ prospect industry: " + invalid_industry + ") "
        elif (
            icp_scoring_ruleset.included_individual_industry_keywords
            and enriched_prospect_company.prospect_industry
            and any(
                keyword.lower() in enriched_prospect_company.prospect_industry.lower()
                for keyword in icp_scoring_ruleset.included_individual_industry_keywords
            )
        ):
            score += 1
            valid_industry = ""
            for keyword in icp_scoring_ruleset.included_individual_industry_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.prospect_industry.lower()
                ):
                    valid_industry = keyword
                    break
            reasoning += "(✅ prospect industry: " + valid_industry + ") "

        # Prospect Years of Experience
        if (
            enriched_prospect_company.prospect_years_of_experience
            and (
                icp_scoring_ruleset.individual_years_of_experience_start
                and enriched_prospect_company.prospect_years_of_experience
                and enriched_prospect_company.prospect_years_of_experience
                >= icp_scoring_ruleset.individual_years_of_experience_start
            )
            and (
                icp_scoring_ruleset.individual_years_of_experience_end
                and icp_scoring_ruleset.individual_years_of_experience_end
                and enriched_prospect_company.prospect_years_of_experience
                <= icp_scoring_ruleset.individual_years_of_experience_end
            )
        ):
            score += 1
            reasoning += (
                "(✅ prospect years of experience: "
                + str(enriched_prospect_company.prospect_years_of_experience)
                + ") "
            )
        elif enriched_prospect_company.prospect_years_of_experience and (
            (
                icp_scoring_ruleset.individual_years_of_experience_start
                and enriched_prospect_company.prospect_years_of_experience
                and enriched_prospect_company.prospect_years_of_experience
                < icp_scoring_ruleset.individual_years_of_experience_start
            )
            or (
                icp_scoring_ruleset.individual_years_of_experience_end
                and icp_scoring_ruleset.individual_years_of_experience_end
                and enriched_prospect_company.prospect_years_of_experience
                > icp_scoring_ruleset.individual_years_of_experience_end
            )
        ):
            score -= num_attributes
            reasoning += (
                "(❌ prospect years of experience: "
                + str(enriched_prospect_company.prospect_years_of_experience)
                + ") "
            )

        # Prospect Skillz
        if (
            icp_scoring_ruleset.excluded_individual_skills_keywords
            and enriched_prospect_company.prospect_skills
            and any(
                keyword.lower() in skill.lower()
                for skill in enriched_prospect_company.prospect_skills
                for keyword in icp_scoring_ruleset.excluded_individual_skills_keywords
            )
        ):
            score -= num_attributes
            invalid_skill = ""
            for keyword in icp_scoring_ruleset.excluded_individual_skills_keywords:
                for skill in enriched_prospect_company.prospect_skills:
                    if keyword.lower() in skill.lower():
                        invalid_skill = keyword
                        break
            reasoning += "(❌ prospect skills: " + invalid_skill + ") "
        elif (
            icp_scoring_ruleset.included_individual_skills_keywords
            and enriched_prospect_company.prospect_skills
            and any(
                keyword.lower() in skill.lower()
                for skill in enriched_prospect_company.prospect_skills
                for keyword in icp_scoring_ruleset.included_individual_skills_keywords
            )
        ):
            score += 1
            valid_skill = ""
            for keyword in icp_scoring_ruleset.included_individual_skills_keywords:
                for skill in enriched_prospect_company.prospect_skills:
                    if keyword.lower() in skill.lower():
                        valid_skill = keyword
                        break
            reasoning += "(✅ prospect skills: " + valid_skill + ") "

        # Locations Keywords
        if (
            icp_scoring_ruleset.excluded_individual_locations_keywords
            and enriched_prospect_company.prospect_location
            and any(
                keyword.lower() in enriched_prospect_company.prospect_location.lower()
                for keyword in icp_scoring_ruleset.excluded_individual_locations_keywords
            )
        ):
            score -= num_attributes
            invalid_location = ""
            for keyword in icp_scoring_ruleset.excluded_individual_locations_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.prospect_location.lower()
                ):
                    invalid_location = keyword
                    break
            reasoning += "(❌ prospect location: " + invalid_location + ") "
        elif (
            icp_scoring_ruleset.included_individual_locations_keywords
            and enriched_prospect_company.prospect_location
            and any(
                keyword.lower() in enriched_prospect_company.prospect_location.lower()
                for keyword in icp_scoring_ruleset.included_individual_locations_keywords
            )
        ):
            score += 1
            valid_location = ""
            for keyword in icp_scoring_ruleset.included_individual_locations_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.prospect_location.lower()
                ):
                    valid_location = keyword
                    break
            reasoning += "(✅ prospect location: " + valid_location + ") "

        # Prospect Generalized Keywords
        if (
            icp_scoring_ruleset.excluded_individual_generalized_keywords
            and enriched_prospect_company.prospect_dump
            and any(
                keyword.lower() in enriched_prospect_company.prospect_dump.lower()
                for keyword in icp_scoring_ruleset.excluded_individual_generalized_keywords
            )
        ):
            score -= num_attributes
            invalid_generalized = ""
            for keyword in icp_scoring_ruleset.excluded_individual_generalized_keywords:
                if keyword.lower() in enriched_prospect_company.prospect_dump.lower():
                    invalid_generalized = keyword
                    break
            reasoning += "(❌ general prospect info: " + invalid_generalized + ") "
        elif (
            icp_scoring_ruleset.included_individual_generalized_keywords
            and enriched_prospect_company.prospect_dump
            and any(
                keyword.lower() in enriched_prospect_company.prospect_dump.lower()
                for keyword in icp_scoring_ruleset.included_individual_generalized_keywords
            )
        ):
            score += 1
            valid_generalized = ""
            for keyword in icp_scoring_ruleset.included_individual_generalized_keywords:
                if keyword.lower() in enriched_prospect_company.prospect_dump.lower():
                    valid_generalized = keyword
                    break
            reasoning += "(✅ general prospect info: " + valid_generalized + ") "

        # Company Name
        if (
            icp_scoring_ruleset.excluded_company_name_keywords
            and enriched_prospect_company.company_name
            and any(
                keyword.lower() in enriched_prospect_company.company_name.lower()
                for keyword in icp_scoring_ruleset.excluded_company_name_keywords
            )
        ):
            score -= num_attributes
            invalid_company_name = ""
            for keyword in icp_scoring_ruleset.excluded_company_name_keywords:
                if keyword.lower() in enriched_prospect_company.company_name.lower():
                    invalid_company_name = keyword
                    break
            reasoning += "(❌ company name: " + invalid_company_name + ") "
        elif (
            icp_scoring_ruleset.included_company_name_keywords
            and enriched_prospect_company.company_name
            and any(
                keyword.lower() in enriched_prospect_company.company_name.lower()
                for keyword in icp_scoring_ruleset.included_company_name_keywords
            )
        ):
            score += 1
            valid_company_name = ""
            for keyword in icp_scoring_ruleset.included_company_name_keywords:
                if keyword.lower() in enriched_prospect_company.company_name.lower():
                    valid_company_name = keyword
                    break
            reasoning += "(✅ company name: " + valid_company_name + ") "

        # Company Location Keywords
        if (
            icp_scoring_ruleset.excluded_company_locations_keywords
            and enriched_prospect_company.company_location
            and any(
                keyword.lower() in enriched_prospect_company.company_location.lower()
                for keyword in icp_scoring_ruleset.excluded_company_locations_keywords
            )
        ):
            score -= num_attributes
            invalid_company_location = ""
            for keyword in icp_scoring_ruleset.excluded_company_locations_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.company_location.lower()
                ):
                    invalid_company_location = keyword
                    break
            reasoning += "(❌ company location: " + invalid_company_location + ") "
        elif (
            icp_scoring_ruleset.included_company_locations_keywords
            and enriched_prospect_company.company_location
            and any(
                keyword.lower() in enriched_prospect_company.company_location.lower()
                for keyword in icp_scoring_ruleset.included_company_locations_keywords
            )
        ):
            score += 1
            valid_company_location = ""
            for keyword in icp_scoring_ruleset.included_company_locations_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.company_location.lower()
                ):
                    valid_company_location = keyword
                    break
            reasoning += "(✅ company location: " + valid_company_location + ") "

        # Company Size
        if enriched_prospect_company.company_employee_count != "None" and (
            (
                icp_scoring_ruleset.company_size_start
                and enriched_prospect_company.company_employee_count
                and int(enriched_prospect_company.company_employee_count)
                >= icp_scoring_ruleset.company_size_start
            )
            and (
                icp_scoring_ruleset.company_size_end
                and int(enriched_prospect_company.company_employee_count)
                <= icp_scoring_ruleset.company_size_end
            )
        ):
            score += 1
            size = ""
            if icp_scoring_ruleset.company_size_start:
                size += str(icp_scoring_ruleset.company_size_start)
            size += "-"
            if icp_scoring_ruleset.company_size_end:
                size += str(icp_scoring_ruleset.company_size_end)
            reasoning += (
                "(✅ company size: "
                + str(enriched_prospect_company.company_employee_count)
                + ") "
            )
        elif enriched_prospect_company.company_employee_count != "None" and (
            (
                icp_scoring_ruleset.company_size_start
                and enriched_prospect_company.company_employee_count
                and int(enriched_prospect_company.company_employee_count)
                < icp_scoring_ruleset.company_size_start
            )
            or (
                icp_scoring_ruleset.company_size_end
                and int(enriched_prospect_company.company_employee_count)
                > icp_scoring_ruleset.company_size_end
            )
        ):
            score -= num_attributes
            size = ""
            if icp_scoring_ruleset.company_size_start:
                size += str(icp_scoring_ruleset.company_size_start)
            size += "-"
            if icp_scoring_ruleset.company_size_end:
                size += str(icp_scoring_ruleset.company_size_end)
            reasoning += (
                "(❌ company size: "
                + str(enriched_prospect_company.company_employee_count)
                + ") "
            )

        # Company Industry
        if (
            icp_scoring_ruleset.excluded_company_industries_keywords
            and enriched_prospect_company.prospect_industry
            and any(
                keyword.lower() in enriched_prospect_company.prospect_industry.lower()
                for keyword in icp_scoring_ruleset.excluded_company_industries_keywords
            )
        ):
            score -= num_attributes
            invalid_industry = ""
            for keyword in icp_scoring_ruleset.excluded_company_industries_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.prospect_industry.lower()
                ):
                    invalid_industry = keyword
                    break
            reasoning += "(❌ company industry: " + invalid_industry + ") "
        elif (
            icp_scoring_ruleset.included_company_industries_keywords
            and enriched_prospect_company.prospect_industry
            and any(
                keyword.lower() in enriched_prospect_company.prospect_industry.lower()
                for keyword in icp_scoring_ruleset.included_company_industries_keywords
            )
        ):
            score += 1
            valid_industry = ""
            for keyword in icp_scoring_ruleset.included_company_industries_keywords:
                if (
                    keyword.lower()
                    in enriched_prospect_company.prospect_industry.lower()
                ):
                    valid_industry = keyword
                    break
            reasoning += "(✅ company industry: " + valid_industry + ") "

        # Company Generalized Keywords
        if (
            icp_scoring_ruleset.excluded_company_generalized_keywords
            and enriched_prospect_company.company_dump
            and any(
                keyword.lower() in enriched_prospect_company.company_dump.lower()
                for keyword in icp_scoring_ruleset.excluded_company_generalized_keywords
            )
        ):
            score -= num_attributes
            invalid_generalized = ""
            for keyword in icp_scoring_ruleset.excluded_company_generalized_keywords:
                if keyword.lower() in enriched_prospect_company.company_dump.lower():
                    invalid_generalized = keyword
                    break
            reasoning += "(❌ company general info: " + invalid_generalized + ") "
        elif (
            icp_scoring_ruleset.included_company_generalized_keywords
            and enriched_prospect_company.company_dump
            and any(
                keyword.lower() in enriched_prospect_company.company_dump.lower()
                for keyword in icp_scoring_ruleset.included_company_generalized_keywords
            )
        ):
            score += 1
            valid_generalized = ""
            for keyword in icp_scoring_ruleset.included_company_generalized_keywords:
                if keyword.lower() in enriched_prospect_company.company_dump.lower():
                    valid_generalized = keyword
                    break
            reasoning += "(✅ company general info: " + valid_generalized + ") "

        if queue:
            queue.put((enriched_prospect_company, score, reasoning))

        db.session.close()

        return (enriched_prospect_company, score, reasoning)


@celery.task(bind=True, max_retries=3)
def apply_icp_scoring_ruleset_filters_task(
    self, client_archetype_id: int, prospect_ids: list[int]
):
    try:
        apply_icp_scoring_ruleset_filters(client_archetype_id, prospect_ids)

        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e)

    return False


def apply_icp_scoring_ruleset_filters(
    client_archetype_id: int, prospect_ids: list[int]
):
    """
    Apply the ICP scoring ruleset to all prospects in the client archetype.
    """
    num_attributes = count_num_icp_attributes(client_archetype_id)

    # Step 1: Get the raw prospect list with data enriched
    print("Pulling raw enriched prospect companies list...")
    raw_enriched_prospect_companies_list = get_raw_enriched_prospect_companies_list(
        client_archetype_id=client_archetype_id,
        prospect_ids=prospect_ids,
    )
    print(
        "Pulled raw enriched prospect companies list with length: "
        + str(len(raw_enriched_prospect_companies_list))
    )

    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()

    # Step 2: Score all the prospects
    print("Scoring prospects...")
    score_map = {}
    entries = raw_enriched_prospect_companies_list.items()
    raw_data = []

    results_queue = queue.Queue()
    max_threads = 5

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:

        futures = []
        for (
            prospect_id,
            enriched_prospect_company,
        ) in tqdm(entries):
            futures.append(
                executor.submit(
                    score_one_prospect,
                    enriched_prospect_company=enriched_prospect_company,
                    icp_scoring_ruleset=icp_scoring_ruleset,
                    queue=results_queue,
                )
            )

        concurrent.futures.wait(futures)

    while not results_queue.empty():
        result = results_queue.get()
        enriched_company: EnrichedProspectCompany = result[0]
        score = result[1]
        reasoning = result[2]

        prospect_id = enriched_company.prospect_id

        if score not in score_map:
            score_map[score] = 0
        score_map[score] += 1

        raw_data.append(
            {
                "prospect_id": prospect_id,
                "score": score,
                "reasoning": reasoning,
            }
        )

    # Determine the labels (VERY HIGH -> VERY LOW)
    sorted_keys = sorted(score_map.keys())
    minimum_key = min(score_map.keys()) if len(score_map.keys()) > 0 else 0
    mid_minimum_key = minimum_key // 2
    maximum_key = max(score_map.keys()) if len(score_map.keys()) > 0 else 0
    mid_maximum_key = maximum_key // 2

    label_map = {}
    for i in range(minimum_key - 1, maximum_key + 1):
        if minimum_key - 1 < i and i < mid_minimum_key:
            label_map[i] = 0
        elif mid_minimum_key <= i and i < 0:
            label_map[i] = 1
        elif i == 0:
            label_map[i] = 2
        elif 0 < i and i < mid_maximum_key + 1:
            label_map[i] = 3
        elif mid_maximum_key + 1 <= i and i < maximum_key + 1:
            label_map[i] = 4

    for key in sorted_keys:
        # print '#' symbol for every 5 prospects
        label = str(label_map[key])

        hashtags = "#" * (score_map[key] // 5) + " " + str(score_map[key])

        print(label + ": " + hashtags)

    # Step 4: Batch Update all the prospects
    update_mappings = []
    for entry in raw_data:
        prospect_id = entry["prospect_id"]
        score = entry["score"]
        reasoning = entry["reasoning"]
        if not reasoning:
            reasoning = "🟨 Nothing detected in prospect's profile that matches the ICP scoring ruleset."
        label = label_map[score]

        update_mappings.append(
            {
                "id": prospect_id,
                "icp_fit_score": label,
                "icp_fit_reason": reasoning,
            }
        )

    print("Updating prospects...")
    for batch in tqdm(
        [update_mappings[i : i + 50] for i in range(0, len(update_mappings), 50)]
    ):
        if prospect_ids and len(prospect_ids) <= 50:
            update_prospects(batch)
        else:
            update_prospects.apply_async(args=[batch], priority=1)

    print("Done!")
    return True


@celery.task(bind=True, max_retries=3)
def update_prospects(self, update_mappings):
    try:
        db.session.bulk_update_mappings(Prospect, update_mappings)
        db.session.commit()
        db.session.close()
    except Exception as e:
        db.session.rollback()
        db.session.close()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def move_selected_prospects_to_unassigned(prospect_ids: list[int]):
    """
    Move selected prospects to unassigned contact archetype.
    """
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids),
    ).all()

    if not prospects:
        return False

    client_archetype_id: int = prospects[0].archetype_id
    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    client_sdr_id: int = client_archetype.client_sdr_id
    client_sdr_unassigned_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == True,
    ).first()

    if not client_sdr_unassigned_archetype:
        return False

    bulk_updates = []
    for prospect in prospects:
        prospect.archetype_id = client_sdr_unassigned_archetype.id
        prospect.icp_fit_score = None
        prospect.icp_fit_reason = None
        bulk_updates.append(prospect)

    print(
        "Moving "
        + str(len(bulk_updates))
        + " prospects to unassigned contact archetype..."
    )

    db.session.bulk_save_objects(bulk_updates)
    db.session.commit()
    db.session.close()

    return True
