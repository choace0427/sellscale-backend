import requests
import json
import os
from app import db, celery
from src.client.models import ClientArchetype
from src.prospecting.models import Prospect
from src.research.website.general_website_transformer import (
    generate_general_website_research_points,
)
from src.utils.abstract.attr_utils import deep_get


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


def get_research_payload_new(prospect_id: int, test_mode: bool):
    if test_mode:
        return SAMPLE_RESEARCH_RESPONSE

    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.get(prospect_id)

    rp: ResearchPayload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    if rp:
        return rp.payload

    personal_info = {}
    company_info = {}
    linkedin_url = p.linkedin_url
    if linkedin_url:
        linkedin_slug = linkedin_url.split("/in/")[1]
        if linkedin_slug:
            personal_info = research_personal_profile_details(profile_id=linkedin_slug)
            try:
                if len(personal_info.get("position_groups", [])) > 0:
                    company_name = (
                        personal_info.get("position_groups", [])[0]
                        .get("company", {})
                        .get("url", "")
                        .split("company/")[1]
                        .replace("/", "")
                    )
                    company_info = research_corporate_profile_details(
                        company_name=company_name
                    )
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

    prospect: Prospect = Prospect.query.get(prospect_id)
    company_url_update = deep_get(payload, "company.details.urls.company_page")
    if company_url_update:
        prospect.company_url = company_url_update
    db.session.add(prospect)
    db.session.commit()

    return payload


def get_research_and_bullet_points_new(prospect_id: int, test_mode: bool):
    info = get_research_payload_new(prospect_id=prospect_id, test_mode=test_mode)
    prospect: Prospect = Prospect.query.get(prospect_id)

    company_url = str(prospect.company_url)
    archetype_id = prospect.archetype_id
    ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
    blocked_transformers = ca.transformer_blocklist

    research_payload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    research_payload_id = research_payload and research_payload.id

    linkedin_transformers = [
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
        (
            ResearchPointType.GENERAL_WEBSITE_TRANSFORMER,
            "general_website_transformer",
            generate_general_website_research_points,
        ),
        # (
        #     ResearchPointType
        # ),
    ]

    bullets = {}

    for t in linkedin_transformers:
        try:
            rp_exists: ResearchPoints = ResearchPoints.query.filter(
                ResearchPoints.research_payload_id == research_payload_id,
                ResearchPoints.research_point_type == t[0],
            ).first()
            if rp_exists:
                bullets[t[1]] = rp_exists.value
                continue

            if blocked_transformers and t[0] in blocked_transformers:
                continue

            if t[0] == ResearchPointType.GENERAL_WEBSITE_TRANSFORMER:
                input_payload = company_url
            else:
                input_payload = info

            value = t[2](input_payload).get("response", "")

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


def reset_prospect_approved_status(prospect_id: int):
    p: Prospect = Prospect.query.get(prospect_id)
    if not p or not p.approved_outreach_message_id:
        return False

    p.approved_outreach_message_id = None
    db.session.add(p)
    db.session.commit()

    return True


def delete_research_points_and_payload_by_prospect_id(prospect_id: int):
    research_payload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    if not research_payload:
        return
    research_payload_id = research_payload.id

    research_points: list = ResearchPoints.query.filter(
        ResearchPoints.research_payload_id == research_payload_id
    ).all()
    for rp in research_points:
        db.session.delete(rp)
        db.session.commit()

    db.session.delete(research_payload)
    db.session.commit()


@celery.task
def reset_prospect_research_and_messages(prospect_id: int):
    from src.message_generation.services import delete_message_generation_by_prospect_id

    reset_prospect_approved_status(prospect_id=prospect_id)
    delete_message_generation_by_prospect_id(prospect_id=prospect_id)
    delete_research_points_and_payload_by_prospect_id(prospect_id=prospect_id)


def reset_batch_of_prospect_research_and_messages(prospect_ids: list):
    for p_id in prospect_ids:
        reset_prospect_research_and_messages.delay(prospect_id=p_id)
