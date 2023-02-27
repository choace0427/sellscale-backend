from app import celery, db

from src.client.models import Client, ClientArchetype
from src.prospecting.models import Prospect
from src.research.models import (
    ResearchPayload,
    ResearchPoints,
    ResearchPointType,
    ResearchType,
    IScraperPayloadCache,
    IScraperPayloadType,
)
from src.research.website.serp_news_extractor_transformer import (
    SerpNewsExtractorTransformer,
)
from src.research.services import create_iscraper_payload_cache
from src.research.linkedin.extractors.experience import (
    get_current_experience_description,
    get_linkedin_bio_summary,
    get_list_of_past_jobs,
    get_years_of_experience,
    get_years_of_experience_at_current_job,
)
from src.research.linkedin.extractors.projects import get_recent_patent
from src.research.linkedin.extractors.recommendations import (
    get_recent_recommendation_summary,
)
from src.research.website.general_website_transformer import (
    generate_general_website_research_points,
)
from src.utils.abstract.attr_utils import deep_get
from src.utils.converters.string_converters import clean_company_name
from .extractors.current_company import (
    get_current_company_description,
    get_current_company_specialties,
)
from ..sample_research_response import SAMPLE_RESEARCH_RESPONSE

import json
import os
import requests
from datetime import datetime, timedelta

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


def get_research_payload_new(prospect_id: int, test_mode: bool = False):
    from src.prospecting.services import (
        get_linkedin_slug_from_url,
        get_navigator_slug_from_url,
    )

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

    # Check if we have a payload cache for the prospect
    iscraper_personal_cache: IScraperPayloadCache = (
        IScraperPayloadCache.get_iscraper_payload_cache_by_linkedin_url(
            linkedin_url=p.linkedin_url,
        )
    )
    if iscraper_personal_cache and iscraper_personal_cache.created_at > (
        datetime.now() - timedelta(weeks=2)
    ):
        personal_info = json.loads(iscraper_personal_cache.payload)
    else:
        # Get LinkedIn Slug and iScraper payload
        url = p.linkedin_url
        if "/in/" in url:
            slug = get_linkedin_slug_from_url(url)
        elif "/lead/" in url:
            slug = get_navigator_slug_from_url(url)
        personal_info = research_personal_profile_details(profile_id=slug)

        # Add to cache
        create_iscraper_payload_cache(
            linkedin_url=p.linkedin_url,
            payload=personal_info,
            payload_type=IScraperPayloadType.PERSONAL,
        )

    # Get company info
    # Check if we have a payload cache for the company
    company_url = deep_get(personal_info, "position_groups.0.company.url")
    iscraper_company_cache: IScraperPayloadCache = (
        IScraperPayloadCache.get_iscraper_payload_cache_by_linkedin_url(
            linkedin_url=deep_get(personal_info, "position_groups.0.company.url"),
        )
    )
    if iscraper_company_cache and iscraper_company_cache.created_at > (
        datetime.now() - timedelta(weeks=2)
    ):
        company_info = iscraper_company_cache.payload
    else:
        # Get iScraper payload
        company_slug = company_url.split("company/")[1].replace("/", "")
        company_info = research_corporate_profile_details(company_name=company_slug)

        # Add to cache
        create_iscraper_payload_cache(
            linkedin_url=company_url,
            payload=company_info,
            payload_type=IScraperPayloadType.COMPANY,
        )

    # Construct entire payload
    payload = {"personal": personal_info, "company": company_info}
    payload = sanitize_payload(payload)

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


def sanitize_payload(payload: dict):
    """Sanitize payload to remove any empty values

    Sanitizes:
    - Cleans company names
    """
    personal_payload = payload.get("personal", {})
    company_payload = payload.get("company", {})

    if personal_payload:
        position_groups = personal_payload.get("position_groups", [])
        for position in position_groups:
            if position.get("company", {}).get("name"):
                position["company"]["name"] = clean_company_name(
                    position["company"]["name"]
                )

    if company_payload:
        current_company_name = company_payload.get("details", {}).get("name")
        if current_company_name:
            company_payload["details"]["name"] = clean_company_name(
                current_company_name
            )

    new_payload = {"personal": personal_payload, "company": company_payload}

    return new_payload


def get_iscraper_payload_error(payload: dict) -> str:
    """Get errors from iscraper payload"""
    if not payload:
        return "iScraper error not provided"
    elif deep_get(payload, "first_name"):
        raise ValueError("No error in payload")

    message = deep_get(payload, "message")
    if message:
        return message

    detail = deep_get(payload, "detail")
    if detail:
        return detail

    return "iScraper error not provided"


def get_research_and_bullet_points_new(prospect_id: int, test_mode: bool):
    info = get_research_payload_new(prospect_id=prospect_id, test_mode=test_mode)
    prospect: Prospect = Prospect.query.get(prospect_id)

    str(prospect.company_url)
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
        # (
        #     ResearchPointType.YEARS_OF_EXPERIENCE,
        #     "years_of_experience",
        #     get_years_of_experience,
        # ),
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
        (
            ResearchPointType.RECENT_PATENTS,
            "recent_patent",
            get_recent_patent,
        ),
        (
            ResearchPointType.RECENT_RECOMMENDATIONS,
            "recent_recommendation",
            get_recent_recommendation_summary,
        ),
        # (
        #     ResearchPointType.GENERAL_WEBSITE_TRANSFORMER,
        #     "general_website_transformer",
        #     generate_general_website_research_points,
        # ),
        (
            ResearchPointType.LINKEDIN_BIO_SUMMARY,
            "linkedin_bio_summary",
            get_linkedin_bio_summary,
        ),
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

            # if t[0] == ResearchPointType.GENERAL_WEBSITE_TRANSFORMER:
            #     input_payload = company_url
            # else:
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

    client: Client = Client.query.get(prospect.client_id)
    if client.id == 9:  # TODO only run for AdQuick for now
        print("Running SERP Extractor for AdQuick")
        serp_extractor = SerpNewsExtractorTransformer(prospect_id=prospect_id)
        serp_extractor.run()

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
    research_payloads = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).all()
    if len(research_payloads) == 0:
        return

    for research_payload in research_payloads:
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
