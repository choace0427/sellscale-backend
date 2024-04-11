import datetime
import json
import yaml
from multiprocessing import process
from typing import Counter, Optional

from flask import app
import pandas as pd
from pyparsing import dictOf
from src.ml.services import get_text_generation
from src.client.models import ClientArchetype
from src.prospecting.icp_score.models import (
    ICPScoringJobQueue,
    ICPScoringJobQueueStatus,
    ICPScoringRuleset,
)
from app import db, app, celery
from src.prospecting.models import Prospect, ProspectOverallStatus, ProspectStatus
from model_import import ResearchPayload
from src.utils.abstract.attr_utils import deep_get
from sqlalchemy.sql.expression import func
from tqdm import tqdm
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
import hashlib

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
    prospect_education_1: str
    prospect_education_2: str

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
    included_individual_education_keywords: list,
    excluded_individual_education_keywords: list,
    included_individual_seniority_keywords: list,
    excluded_individual_seniority_keywords: list,
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
    icp_scoring_ruleset.included_individual_education_keywords = (
        included_individual_education_keywords
    )
    icp_scoring_ruleset.excluded_individual_education_keywords = (
        excluded_individual_education_keywords
    )
    icp_scoring_ruleset.included_individual_seniority_keywords = (
        included_individual_seniority_keywords
    )
    icp_scoring_ruleset.excluded_individual_seniority_keywords = (
        excluded_individual_seniority_keywords
    )

    db.session.add(icp_scoring_ruleset)
    db.session.commit()

    hash = get_ruleset_hash(client_archetype_id)
    icp_scoring_ruleset.hash = hash
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
        icp_scoring_ruleset.included_individual_seniority_keywords
        or icp_scoring_ruleset.excluded_individual_seniority_keywords
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
    if (
        icp_scoring_ruleset.included_individual_education_keywords
        or icp_scoring_ruleset.excluded_individual_education_keywords
    ):
        count += 1

    return count


def get_raw_enriched_prospect_companies_list(
    client_archetype_id: int,
    prospect_ids: Optional[list[int]] = None,
    is_lookalike_profile_only: bool = False,
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
            Prospect.education_1.label("education_1"),
            Prospect.education_2.label("education_2"),
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
            Prospect.education_1,
            Prospect.education_2,
        )
    )

    if is_lookalike_profile_only:
        entries = entries.filter(Prospect.is_lookalike_profile == True)

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
            and deep_get(
                processed[prospect_id].prospect_positions[-1], "date.start.year"
            )
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
        processed[prospect_id].prospect_education_1 = entry[8]
        processed[prospect_id].prospect_education_2 = entry[9]

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
                    reasoning += "(✅ prospect title: " + valid_title + ") "

        # Prospect Seniority
        if (
            icp_scoring_ruleset.excluded_individual_seniority_keywords
            and enriched_prospect_company.prospect_title
            and any(
                keyword.lower() in enriched_prospect_company.prospect_title.lower()
                for keyword in icp_scoring_ruleset.excluded_individual_seniority_keywords
            )
        ):
            score -= num_attributes
            # find the invalid title
            invalid_title = ""
            for keyword in icp_scoring_ruleset.excluded_individual_seniority_keywords:
                if keyword.lower() in enriched_prospect_company.prospect_title.lower():
                    invalid_title = keyword
                    break
            reasoning += "(❌ prospect seniority: " + invalid_title + ") "
        elif (
            icp_scoring_ruleset.included_individual_seniority_keywords
            and enriched_prospect_company.prospect_title
            and any(
                keyword.lower() in enriched_prospect_company.prospect_title.lower()
                for keyword in icp_scoring_ruleset.included_individual_seniority_keywords
            )
        ):
            score += 1
            valid_title = ""
            for keyword in icp_scoring_ruleset.included_individual_seniority_keywords:
                if keyword.lower() in enriched_prospect_company.prospect_title.lower():
                    valid_title = keyword
                    reasoning += "(✅ prospect seniority: " + valid_title + ") "

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
        elif icp_scoring_ruleset.included_individual_locations_keywords:
            score -= num_attributes
            reasoning += "(❌ prospect location: No Match) "

        # Prospect Education
        educations = []
        if enriched_prospect_company.prospect_education_1:
            educations.append(enriched_prospect_company.prospect_education_1)
        if enriched_prospect_company.prospect_education_2:
            educations.append(enriched_prospect_company.prospect_education_2)
        if (
            icp_scoring_ruleset.excluded_individual_education_keywords
            and educations
            and any(
                keyword.lower() in education.lower()
                for education in educations
                for keyword in icp_scoring_ruleset.excluded_individual_education_keywords
            )
        ):
            score -= num_attributes
            invalid_education = ""
            for keyword in icp_scoring_ruleset.excluded_individual_education_keywords:
                for education in educations:
                    if keyword.lower() in education.lower():
                        invalid_education = keyword
                        break
            reasoning += "(❌ prospect education: " + invalid_education + ") "
        elif (
            icp_scoring_ruleset.included_individual_education_keywords
            and educations
            and any(
                keyword.lower() in education.lower()
                for education in educations
                for keyword in icp_scoring_ruleset.included_individual_education_keywords
            )
        ):
            score += 1
            valid_education = ""
            for keyword in icp_scoring_ruleset.included_individual_education_keywords:
                for education in educations:
                    if keyword.lower() in education.lower():
                        valid_education = keyword
                        break
            reasoning += "(✅ prospect education: " + valid_education + ") "

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
        elif icp_scoring_ruleset.included_company_locations_keywords:
            score -= num_attributes
            reasoning += "(❌ company location: No Match)"

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


def apply_icp_scoring_ruleset_filters_task(
    client_archetype_id: int,
    icp_scoring_job_queue_id: Optional[int] = None,
    prospect_ids: Optional[list[int]] = None,
    manual_trigger: Optional[list[int]] = None,
) -> bool:
    """Creates an ICPScoringJobQueue object and begins the icp_scoring job

    Args:
        client_archetype_id (int): ID of the ClientArchetype object
        icp_scoring_job_queue_id (Optional[int], optional): ID of the ICPScoringJobQueue object. Defaults to None.
        prospect_ids (Optional[list[int]], optional): List of prospect IDs to score. Defaults to None.

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the ClientArchetype
    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()

    # Get the ClientSDR ID
    client_sdr_id = client_archetype.client_sdr_id

    # If there is already an ICPScoringJobQueue object, trigger the job
    if icp_scoring_job_queue_id:
        if prospect_ids and len(prospect_ids) <= 50:
            apply_icp_scoring_ruleset_filters(
                icp_scoring_job_id=icp_scoring_job_queue_id,
                client_archetype_id=client_archetype_id,
                prospect_ids=prospect_ids,
            )
        else:
            apply_icp_scoring_ruleset_filters.apply_async(
                args=[icp_scoring_job_queue_id, client_archetype_id],
                queue="icp_scoring",
                routing_key="icp_scoring",
            )

        return True

    if prospect_ids == None:
        # Get Prospects that belong in this ClientArchetype
        prospects = Prospect.query.filter_by(archetype_id=client_archetype_id).all()
        prospect_ids = [prospect.id for prospect in prospects]

    # Create ICPScoringJobQueue object
    icp_scoring_job = ICPScoringJobQueue(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        prospect_ids=prospect_ids,
        manual_trigger=manual_trigger,
    )
    db.session.add(icp_scoring_job)
    db.session.commit()

    if prospect_ids and len(prospect_ids) <= 50:
        apply_icp_scoring_ruleset_filters(
            icp_scoring_job_id=icp_scoring_job.id,
            client_archetype_id=client_archetype_id,
            prospect_ids=prospect_ids,
        )
    else:
        apply_icp_scoring_ruleset_filters.apply_async(
            args=[icp_scoring_job.id, client_archetype_id, prospect_ids],
            queue="icp_scoring",
            routing_key="icp_scoring",
        )

    return True


@celery.task(bind=True, max_retries=3)
def apply_icp_scoring_ruleset_filters(
    self,
    icp_scoring_job_id: int,
    client_archetype_id: int,
    prospect_ids: Optional[list[int]] = None,
):
    try:
        """
        Apply the ICP scoring ruleset to all prospects in the client archetype.
        """
        num_attributes = count_num_icp_attributes(client_archetype_id)

        # Get the scoring job, mark it as in progress
        icp_scoring_job: ICPScoringJobQueue = ICPScoringJobQueue.query.filter_by(
            id=icp_scoring_job_id
        ).first()
        if icp_scoring_job.run_status not in [
            ICPScoringJobQueueStatus.PENDING,
            ICPScoringJobQueueStatus.FAILED,
        ]:
            return
        icp_scoring_job.run_status = ICPScoringJobQueueStatus.IN_PROGRESS
        icp_scoring_job.attempts = (
            icp_scoring_job.attempts + 1 if icp_scoring_job.attempts else 1
        )
        db.session.commit()

        prospect_ids = icp_scoring_job.prospect_ids or prospect_ids
        if not prospect_ids:
            # Get Prospects that belong in this ClientArchetype
            prospects = Prospect.query.filter_by(archetype_id=client_archetype_id).all()
            prospect_ids = [prospect.id for prospect in prospects]
            icp_scoring_job.prospect_ids = prospect_ids

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
                    "icp_fit_last_hash": icp_scoring_ruleset.hash,
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

        # Get the scoring job, mark it as complete
        icp_scoring_job: ICPScoringJobQueue = ICPScoringJobQueue.query.filter_by(
            id=icp_scoring_job_id
        ).first()
        icp_scoring_job.run_status = ICPScoringJobQueueStatus.COMPLETED
        icp_scoring_job.error_message = None
        db.session.commit()

        return True
    except Exception as e:
        db.session.rollback()

        # Get the scoring job, mark it as failed
        icp_scoring_job: ICPScoringJobQueue = ICPScoringJobQueue.query.filter_by(
            id=icp_scoring_job_id
        ).first()
        icp_scoring_job.run_status = ICPScoringJobQueueStatus.FAILED
        icp_scoring_job.error_message = str(e)
        db.session.commit()

        raise self.retry(exc=e)


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
        Prospect.overall_status.in_(
            [
                ProspectOverallStatus.PROSPECTED,
                ProspectOverallStatus.SENT_OUTREACH,
            ]
        ),
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

    if len(prospects) < 100:
        bulk_updates = []
        for prospect in prospects:
            prospect.archetype_id = client_sdr_unassigned_archetype.id
            prospect.approved_outreach_message_id = None
            prospect.status = ProspectStatus.PROSPECTED
            prospect.icp_fit_score = 2
            prospect.icp_fit_reason = "🟨 Moved to Unassigned Persona."
            bulk_updates.append(prospect)

        print(
            "Moving "
            + str(len(bulk_updates))
            + " prospects to unassigned contact archetype..."
        )

        db.session.bulk_save_objects(bulk_updates)
        db.session.commit()
        db.session.close()
    else:
        for prospect in prospects:
            move_prospect_to_unassigned.delay(
                prospect_id=prospect.id,
                client_sdr_unassigned_archetype_id=client_sdr_unassigned_archetype.id,
            )

    return True


@celery.task(bind=True, max_retries=3)
def move_prospect_to_unassigned(
    self, prospect_id: int, client_sdr_unassigned_archetype_id: int
):
    try:
        prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        if not prospect:
            return False

        prospect.archetype_id = client_sdr_unassigned_archetype_id
        prospect.approved_outreach_message_id = None
        prospect.status = ProspectStatus.PROSPECTED
        prospect.icp_fit_score = 2
        prospect.icp_fit_reason = "🟨 Moved to Unassigned Persona."
        db.session.add(prospect)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        db.session.close()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def predict_icp_scoring_filters_from_prospect_id(
    client_archetype_id: int,
):
    enriched_pcs: dict = get_raw_enriched_prospect_companies_list(
        client_archetype_id=client_archetype_id,
        prospect_ids=None,
        is_lookalike_profile_only=True,
    )

    all_titles = [enriched_pcs[key].prospect_title for key in enriched_pcs.keys()]
    # get top 10 titles with highest frequency
    good_titles = [
        title
        for title, count in Counter(all_titles).most_common(10)
        if title and title != "None"
    ]

    all_industries = [
        enriched_pcs[key].prospect_industry for key in enriched_pcs.keys()
    ]
    # get top 10 industries with highest frequency
    good_industries = [
        industry
        for industry, count in Counter(all_industries).most_common(10)
        if industry and industry != "None"
    ]

    all_companies = [enriched_pcs[key].company_name for key in enriched_pcs.keys()]
    # get top 10 companies with highest frequency
    good_companies = [
        company
        for company, count in Counter(all_companies).most_common(10)
        if company and company != "None"
    ]

    min_years_of_experience = min(
        [
            int(enriched_pcs[key].prospect_years_of_experience)
            for key in enriched_pcs.keys()
            if enriched_pcs[key].prospect_years_of_experience
            and enriched_pcs[key].prospect_years_of_experience != "None"
        ]
    )
    max_years_of_experience = max(
        [
            int(enriched_pcs[key].prospect_years_of_experience)
            for key in enriched_pcs.keys()
            if enriched_pcs[key].prospect_years_of_experience
            and enriched_pcs[key].prospect_years_of_experience != "None"
        ]
    )
    min_company_size = min(
        [
            int(enriched_pcs[key].company_employee_count)
            for key in enriched_pcs.keys()
            if enriched_pcs[key].company_employee_count
            and enriched_pcs[key].company_employee_count != "None"
        ]
    )
    max_company_size = max(
        [
            int(enriched_pcs[key].company_employee_count)
            for key in enriched_pcs.keys()
            if enriched_pcs[key].company_employee_count
            and enriched_pcs[key].company_employee_count != "None"
        ]
    )

    return {
        "good_titles": good_titles,
        "good_industries": good_industries,
        "good_companies": good_companies,
        "min_years_of_experience": min_years_of_experience,
        "max_years_of_experience": max_years_of_experience,
        "min_company_size": min_company_size,
        "max_company_size": max_company_size,
    }


def set_icp_scores_to_predicted_values(client_archetype_id: int):
    predicted_filters = predict_icp_scoring_filters_from_prospect_id(
        client_archetype_id=client_archetype_id,
    )

    good_titles = predicted_filters["good_titles"]
    good_industries = predicted_filters["good_industries"]
    good_companies = predicted_filters["good_companies"]
    min_years_of_experience = predicted_filters["min_years_of_experience"]
    max_years_of_experience = predicted_filters["max_years_of_experience"]
    min_company_size = predicted_filters["min_company_size"]
    max_company_size = predicted_filters["max_company_size"]

    success = update_icp_scoring_ruleset(
        client_archetype_id=client_archetype_id,
        included_individual_title_keywords=good_titles,
        excluded_individual_title_keywords=[],
        included_individual_industry_keywords=good_industries,
        excluded_individual_industry_keywords=[],
        individual_years_of_experience_start=min_years_of_experience,
        individual_years_of_experience_end=max_years_of_experience,
        included_individual_skills_keywords=[],
        excluded_individual_skills_keywords=[],
        included_individual_locations_keywords=[
            "United States",
            "Canada",
            "US ",
            "CA ",
        ],
        excluded_individual_locations_keywords=[],
        included_individual_generalized_keywords=[],
        excluded_individual_generalized_keywords=[],
        included_company_name_keywords=good_companies,
        excluded_company_name_keywords=[],
        included_company_locations_keywords=["United States", "Canada", "US ", "CA "],
        excluded_company_locations_keywords=[],
        company_size_start=min_company_size,
        company_size_end=max_company_size,
        included_company_industries_keywords=[],
        excluded_company_industries_keywords=[],
        included_company_generalized_keywords=[],
        excluded_company_generalized_keywords=[],
        included_individual_education_keywords=[],
        excluded_individual_education_keywords=[],
        included_individual_seniority_keywords=[],
        excluded_individual_seniority_keywords=[],
    )

    return success


def clear_icp_ruleset(client_archetype_id: int):
    success = update_icp_scoring_ruleset(
        client_archetype_id=client_archetype_id,
        included_individual_title_keywords=[],
        excluded_individual_title_keywords=[],
        included_individual_industry_keywords=[],
        excluded_individual_industry_keywords=[],
        individual_years_of_experience_start=None,
        individual_years_of_experience_end=None,
        included_individual_skills_keywords=[],
        excluded_individual_skills_keywords=[],
        included_individual_locations_keywords=[],
        excluded_individual_locations_keywords=[],
        included_individual_generalized_keywords=[],
        excluded_individual_generalized_keywords=[],
        included_company_name_keywords=[],
        excluded_company_name_keywords=[],
        included_company_locations_keywords=[],
        excluded_company_locations_keywords=[],
        company_size_start=None,
        company_size_end=None,
        included_company_industries_keywords=[],
        excluded_company_industries_keywords=[],
        included_company_generalized_keywords=[],
        excluded_company_generalized_keywords=[],
        included_individual_education_keywords=[],
        excluded_individual_education_keywords=[],
        included_individual_seniority_keywords=[],
        excluded_individual_seniority_keywords=[],
    )

    return success


def clone_icp_ruleset(source_archetype_id: int, target_archetype_id: int):
    icp_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=source_archetype_id
    ).first()

    if not icp_ruleset:
        return False

    success = update_icp_scoring_ruleset(
        client_archetype_id=target_archetype_id,
        included_individual_title_keywords=icp_ruleset.included_individual_title_keywords,
        excluded_individual_title_keywords=icp_ruleset.excluded_individual_title_keywords,
        included_individual_industry_keywords=icp_ruleset.included_individual_industry_keywords,
        excluded_individual_industry_keywords=icp_ruleset.excluded_individual_industry_keywords,
        individual_years_of_experience_start=icp_ruleset.individual_years_of_experience_start,
        individual_years_of_experience_end=icp_ruleset.individual_years_of_experience_end,
        included_individual_skills_keywords=icp_ruleset.included_individual_skills_keywords,
        excluded_individual_skills_keywords=icp_ruleset.excluded_individual_skills_keywords,
        included_individual_locations_keywords=icp_ruleset.included_individual_locations_keywords,
        excluded_individual_locations_keywords=icp_ruleset.excluded_individual_locations_keywords,
        included_individual_generalized_keywords=icp_ruleset.included_individual_generalized_keywords,
        excluded_individual_generalized_keywords=icp_ruleset.excluded_individual_generalized_keywords,
        included_company_name_keywords=icp_ruleset.included_company_name_keywords,
        excluded_company_name_keywords=icp_ruleset.excluded_company_name_keywords,
        included_company_locations_keywords=icp_ruleset.included_company_locations_keywords,
        excluded_company_locations_keywords=icp_ruleset.excluded_company_locations_keywords,
        company_size_start=icp_ruleset.company_size_start,
        company_size_end=icp_ruleset.company_size_end,
        included_company_industries_keywords=icp_ruleset.included_company_industries_keywords,
        excluded_company_industries_keywords=icp_ruleset.excluded_company_industries_keywords,
        included_company_generalized_keywords=icp_ruleset.included_company_generalized_keywords,
        excluded_company_generalized_keywords=icp_ruleset.excluded_company_generalized_keywords,
        included_individual_education_keywords=icp_ruleset.included_individual_education_keywords,
        excluded_individual_education_keywords=icp_ruleset.excluded_individual_education_keywords,
        included_individual_seniority_keywords=icp_ruleset.included_individual_seniority_keywords,
        excluded_individual_seniority_keywords=icp_ruleset.excluded_individual_seniority_keywords,
    )

    return success


def generate_new_icp_filters(client_archetype_id: int, message: str):
    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()
    if not icp_scoring_ruleset:
        return False

    # Use message to improve the ICP scoring ruleset
    prompt = f"""
I have a list of filters for finding good sales prospects. I'm going to give you the filters and then provide you with a alteration to them. Please make the alteration then return the filters in the exact same format I presented them to you.
The keyword filters are an OR operation, meaning a prospect will match if they match any of the filters. So, unless exprssed otherwise, please add to the filters rather than replace them.

If the alteration is location related, please use the full name of the location (e.g. United States, Canada, etc.) and related locations.
#### Example
Alteration: show me people in the bay area
Prospect Location Keywords: bay area, san francisco, san jose, oakland, berkeley


## Current Filters
Prospect Years of Experience: [{icp_scoring_ruleset.individual_years_of_experience_start}, {icp_scoring_ruleset.individual_years_of_experience_end}]
Company Size: [{icp_scoring_ruleset.company_size_start}, {icp_scoring_ruleset.company_size_end}]
Prospect Title Keywords: {icp_scoring_ruleset.included_individual_title_keywords}
Prospect Industry Keywords: {icp_scoring_ruleset.included_individual_industry_keywords}
Prospect Location Keywords: {icp_scoring_ruleset.included_individual_locations_keywords}
Prospect Skills Keywords: {icp_scoring_ruleset.included_individual_skills_keywords}
Prospect Generalized Keywords: {icp_scoring_ruleset.included_individual_generalized_keywords}
Prospect Education: {icp_scoring_ruleset.included_individual_education_keywords}
Company Name Keywords: {icp_scoring_ruleset.included_company_name_keywords}
Company Location Keywords: {icp_scoring_ruleset.included_company_locations_keywords}
Company Industry Keywords: {icp_scoring_ruleset.included_company_industries_keywords}
Company Generalized Keywords: {icp_scoring_ruleset.included_company_generalized_keywords}

## Alteration
{message}

## Updated Filters
"""

    response = get_text_generation(
        [
            {"role": "user", "content": prompt},
        ],
        temperature=1.0,
        max_tokens=240,
        model="gpt-4",
        type="ICP_CLASSIFY",
    )

    lines = response.strip().split("\n")

    # Initialize an empty dictionary
    icp_dict = {}

    # Define the mapping of keys to attribute names in the ICPScoringRuleset class
    key_to_attribute = {
        "Prospect Years of Experience": (
            "individual_years_of_experience_start",
            "individual_years_of_experience_end",
        ),
        "Company Size": ("company_size_start", "company_size_end"),
        "Prospect Title Keywords": (
            "included_individual_title_keywords",
            "excluded_individual_title_keywords",
        ),
        "Prospect Industry Keywords": (
            "included_individual_industry_keywords",
            "excluded_individual_industry_keywords",
        ),
        "Prospect Location Keywords": (
            "included_individual_locations_keywords",
            "excluded_individual_locations_keywords",
        ),
        "Prospect Skills Keywords": (
            "included_individual_skills_keywords",
            "excluded_individual_skills_keywords",
        ),
        "Prospect Education Keywords": (
            "included_individual_education_keywords",
            "excluded_individual_education_keywords",
        ),
        "Prospect Generalized Keywords": (
            "included_individual_generalized_keywords",
            "excluded_individual_generalized_keywords",
        ),
        "Company Name Keywords": (
            "included_company_name_keywords",
            "excluded_company_name_keywords",
        ),
        "Company Location Keywords": (
            "included_company_locations_keywords",
            "excluded_company_locations_keywords",
        ),
        "Company Industry Keywords": (
            "included_company_industries_keywords",
            "excluded_company_industries_keywords",
        ),
        "Company Generalized Keywords": (
            "included_company_generalized_keywords",
            "excluded_company_generalized_keywords",
        ),
    }

    # Iterate over the lines and populate the icp_dict
    for line in lines:
        if ":" in line:
            key, value = line.split(": ")
            attributes = key_to_attribute.get(key)
            if attributes:
                # Split the values based on brackets and remove leading/trailing whitespace
                values = [v.strip() for v in value.strip("[]").split(", ")]
                if len(values) == 2:
                    start, end = values
                    try:
                        icp_dict[attributes[0]] = (
                            int(start) if start and start != "None" else None
                        )
                        icp_dict[attributes[1]] = (
                            int(end) if end and end != "None" else None
                        )
                    except ValueError:
                        icp_dict[attributes[0]] = None
                        icp_dict[attributes[1]] = None
                else:
                    icp_dict[attributes[0]] = [v.strip("'") for v in values]

    # Create an instance of ICPScoringRuleset and populate it with the values
    icp_ruleset = ICPScoringRuleset(**icp_dict)

    # Convert the ICPScoringRuleset instance to a dictionary
    icp_dict = icp_ruleset.to_dict()

    return icp_dict


def update_icp_filters(client_archetype_id: int, filters, merge=False):
    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()
    if icp_scoring_ruleset:
        # Update the attributes with the values from icp_dict
        for key, value in filters.items():
            if key == "client_archetype_id":
                continue

            if key == "company_size_start":
                start = 0
                end = 1000000
                if value:
                    try:
                        start = int(value[0].split(",")[0])
                        end = int(value[-1].split(",")[1])
                    except:
                        pass
                icp_scoring_ruleset.company_size_start = start
                icp_scoring_ruleset.company_size_end = end
                continue

            if value == ["None"] or value == [""] or value == []:
                setattr(icp_scoring_ruleset, key, None)
            else:
                if merge:
                    if isinstance(value, list):
                        if getattr(icp_scoring_ruleset, key):
                            setattr(
                                icp_scoring_ruleset,
                                key,
                                getattr(icp_scoring_ruleset, key)
                                + [s.replace('"', "") for s in value],
                            )
                        else:
                            setattr(
                                icp_scoring_ruleset,
                                key,
                                [s.replace('"', "") for s in value],
                            )
                    else:
                        if getattr(icp_scoring_ruleset, key):
                            setattr(
                                icp_scoring_ruleset,
                                key,
                                getattr(icp_scoring_ruleset, key) + value,
                            )
                        else:
                            setattr(icp_scoring_ruleset, key, value)

        # Commit the changes to the database
        db.session.commit()

        hash = get_ruleset_hash(client_archetype_id)
        icp_scoring_ruleset.hash = hash
        db.session.commit()

        return True
    else:
        return False


def update_icp_titles_from_sales_nav_url(client_archetype_id: int, sales_nav_url: str):
    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=client_archetype_id
    ).first()
    if not icp_scoring_ruleset:
        return False

    response = get_text_generation(
        [
            {
                "role": "user",
                "content": f"""
Using this Sales Navigator URL:
```
{sales_nav_url}
```

Return a list of the job titles by parsing the URL above and return in a valid JSON formatted as {{data: [titles array]}}

Respond with only the JSON.

JSON:""",
            },
        ],
        max_tokens=600,
        model="gpt-4",
        type="ICP_CLASSIFY",
    )

    titles = []
    try:
        data: dict = yaml.safe_load(response)
        titles = data.get("data", [])
    except:
        return False

    icp_scoring_ruleset.included_individual_title_keywords = (
        icp_scoring_ruleset.included_individual_title_keywords or []
    ) + titles
    db.session.commit()

    return True


def get_ruleset_hash(archetype_id: int):
    icp_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
        client_archetype_id=archetype_id
    ).first()
    if not icp_ruleset:
        return None

    icp_ruleset_dict = icp_ruleset.to_dict()

    return hashlib.md5(
        json.dumps(icp_ruleset_dict, sort_keys=True).encode()
    ).hexdigest()


@celery.task(bind=True, max_retries=3)
def auto_run_icp_scoring():
    archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.is_unassigned_contact_archetype == False,
        ClientArchetype.active == True,
    ).all()

    for archetype in archetypes:
        icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter_by(
            client_archetype_id=archetype.id
        ).first()

        prospects: list[Prospect] = Prospect.query.filter_by(
            archetype_id=archetype.id
        ).all()
        rescore_prospect_ids = [
            prospect.id
            for prospect in prospects
            if prospect.icp_fit_last_hash != icp_scoring_ruleset.hash
        ]

        if len(rescore_prospect_ids) > 0:
            success = apply_icp_scoring_ruleset_filters_task(
                client_archetype_id=archetype.id,
                prospect_ids=rescore_prospect_ids,
            )

            db.session.commit()
