import requests
import json
import os
from app import db

from src.research.models import (
    ResearchPayload,
    ResearchPointType,
    ResearchPoints,
    ResearchType,
)

from .extractors.recommendations import get_recent_recommendation_summary

from .extractors.projects import get_recent_patent

from .extractors.experience import (
    get_current_experience_description,
    get_list_of_past_jobs,
    get_years_of_experience,
    get_years_of_experience_at_current_job,
)

from .extractors.current_company import (
    get_current_company_description,
    get_current_company_specialties,
)

from ..sample_research_response import SAMPLE_RESEARCH_RESPONSE

LINKEDIN_SEARCH_URL = "https://api.iscraper.io/v2/linkedin-search"
PROFILE_DETAILS_URL = "https://api.iscraper.io/v2/profile-details"
DATA_TYPES_URL = "https://api.iscraper.io/v2/data-types"
ISCRAPER_API_KEY = os.environ.get("ISCRAPER_API_KEY")


def research_personal_profile_details(profile_id: str):
    payload = json.dumps(
        {
            "profile_id": profile_id,
            "profile_type": "personal",
            "contact_info": True,
            "recommendations": True,
            "related_profiles": True,
            "network_info": True,
        }
    )
    headers = {"X-API-KEY": ISCRAPER_API_KEY, "Content-Type": "application/json"}

    response = requests.request(
        "POST", PROFILE_DETAILS_URL, headers=headers, data=payload
    )

    return json.loads(response.text)


def research_corporate_profile_details(company_name: str):
    payload = json.dumps(
        {
            "profile_id": company_name,
            "profile_type": "company",
            "contact_info": True,
            "recommendations": True,
            "related_profiles": True,
            "network_info": True,
        }
    )
    headers = {"X-API-KEY": ISCRAPER_API_KEY, "Content-Type": "application/json"}

    response = requests.request(
        "POST", PROFILE_DETAILS_URL, headers=headers, data=payload
    )

    return json.loads(response.text)


def get_research_payload(profile_id: str, test_mode: bool):
    if test_mode:
        return SAMPLE_RESEARCH_RESPONSE

    personal_info = research_personal_profile_details(profile_id=profile_id)
    company_info = {}

    company_info = {}
    try:
        if len(personal_info.get("position_groups", [])) > 0:
            company_name = (
                personal_info.get("position_groups", [])[0]
                .get("company", {})
                .get("url", "")
                .split("company/")[1]
                .replace("/", "")
            )
            company_info = research_corporate_profile_details(company_name=company_name)
    except:
        pass

    return {"personal": personal_info, "company": company_info}


def get_cleaned_response(s: dict):
    if not s:
        return None

    response = s.get("response")
    response = response.replace("\n", "", len(response))
    response = response.split("'")[0]
    return response


def get_research_and_bullet_points(profile_id: str, test_mode: bool):
    info = get_research_payload(profile_id=profile_id, test_mode=test_mode)

    current_company_description = get_current_company_description(data=info)
    current_company_specialties = get_current_company_specialties(data=info)
    current_experience_description = get_current_experience_description(data=info)
    years_of_experience = get_years_of_experience(data=info)
    years_of_experience_at_current_job = get_years_of_experience_at_current_job(
        data=info
    )
    list_of_past_jobs = get_list_of_past_jobs(data=info)
    recent_patent = get_recent_patent(data=info)
    recent_recommendation = get_recent_recommendation_summary(data=info)

    bullets = {
        "current_company_description": get_cleaned_response(
            current_company_description
        ),
        "current_company_specialties": get_cleaned_response(
            current_company_specialties
        ),
        "current_experience_description": get_cleaned_response(
            current_experience_description
        ),
        "years_of_experience": get_cleaned_response(years_of_experience),
        "years_of_experience_at_current_job": get_cleaned_response(
            years_of_experience_at_current_job
        ),
        "list_of_past_jobs": get_cleaned_response(list_of_past_jobs),
        "recent_patent": get_cleaned_response(recent_patent),
        "recent_recommendation": get_cleaned_response(recent_recommendation),
    }

    final_bullets = {}
    for key in bullets:
        if bullets[key]:
            final_bullets[key] = bullets[key].strip()

    return {"raw_data": info, "bullets": final_bullets}

    # ✅  experience: years of experience in industry
    # ✅  experience: years of experience at latest job
    # ✅  experience: worked at X, Y, and Z in the past

    # ✅  current job: ___________ is building the _____________ for ________
    # ✅  current job: came across <company> in the <industry> and saw your profile
    # ✅  current job: <specialities> is such a hot topic these days!

    #    skills: knows X languages: list
    #    skills: studied @ XYZ in _______
    #    skills: recent certificate in _________ X months ago
    #    skills: mention X, Y, Z skills - impressive!

    #    network: Knows X or Y at <current company>?
    #    network: was looking for professionals in _____ in <location>

    #    project: saw that you volunteer at ________
    #    project: saw your websites (blog | youtube | etc) - super cool!  // ( ex. jakob-sagatowski)
    #    project: saw you worked on project w/ __________
    # ✅ project: made patents in X, Y, Z

    # ✅ recommendation: saw ______'s recent recommendation of you. Looks like you're a _________


def get_research_payload_new(prospect_id: int, test_mode: bool):

    if test_mode:
        return SAMPLE_RESEARCH_RESPONSE

    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.get(prospect_id)
    if not p or not p.linkedin_url:
        return None

    rp: ResearchPayload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    if rp:
        return rp.payload

    linkedin_url = p.linkedin_url
    linkedin_slug = linkedin_url.split("/in/")[1]
    if not linkedin_slug:
        return None

    personal_info = research_personal_profile_details(profile_id=linkedin_slug)
    company_info = {}

    company_info = {}
    try:
        if len(personal_info.get("position_groups", [])) > 0:
            company_name = (
                personal_info.get("position_groups", [])[0]
                .get("company", {})
                .get("url", "")
                .split("company/")[1]
                .replace("/", "")
            )
            company_info = research_corporate_profile_details(company_name=company_name)
    except:
        pass

    payload = {"personal": personal_info, "company": company_info}

    rp: ResearchPayload = ResearchPayload(
        prospect_id=prospect_id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload=payload,
    )
    db.session.add(rp)
    db.session.commit()

    return payload


def get_research_and_bullet_points_new(prospect_id: int, test_mode: bool):
    info = get_research_payload_new(prospect_id=prospect_id, test_mode=test_mode)

    research_payload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    research_payload_id = research_payload.id

    transformers = [
        (
            ResearchPointType.CURRENT_JOB_DESCRIPTION,
            "current_company_description",
            get_current_company_description,
        ),
        (
            ResearchPointType.CURRENT_JOB_SPECIALTIES,
            "current_company_specialties",
            get_current_company_specialties,
        ),
        (
            ResearchPointType.CURRENT_EXPERIENCE_DESCRIPTION,
            "current_experience_description",
            get_current_experience_description,
        ),
        (
            ResearchPointType.YEARS_OF_EXPERIENCE,
            "years_of_experience",
            get_years_of_experience,
        ),
        (
            ResearchPointType.YEARS_OF_EXPERIENCE_AT_CURRENT_JOB,
            "years_of_experience_at_current_job",
            get_years_of_experience_at_current_job,
        ),
        (
            ResearchPointType.LIST_OF_PAST_JOBS,
            "list_of_past_jobs",
            get_list_of_past_jobs,
        ),
        (ResearchPointType.RECENT_PATENTS, "recent_patent", get_recent_patent),
        (
            ResearchPointType.RECENT_RECOMMENDATIONS,
            "recent_recommendation",
            get_recent_recommendation_summary,
        ),
    ]

    bullets = {}
    for t in transformers:
        try:
            rp_exists: ResearchPoints = ResearchPoints.query.filter(
                ResearchPoints.research_payload_id == research_payload_id,
                ResearchPoints.research_point_type == t[0],
            ).first()
            if rp_exists:
                bullets[t[1]] = rp_exists.value
                continue

            value = t[2](info).get("response", "")

            if not value:
                continue

            bullets[t[1]] = value

            research_point: ResearchPoints = ResearchPoints(
                research_payload_id=research_payload_id,
                research_point_type=t[0],
                value=value,
            )
            db.session.add(research_point)
            db.session.commit()
        except:
            pass

    final_bullets = {}
    for key in bullets:
        if bullets[key]:
            final_bullets[key] = bullets[key].strip()

    return {"raw_data": info, "bullets": final_bullets}
