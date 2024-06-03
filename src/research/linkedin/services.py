from typing import Optional
from src.company.services import add_company_cache_to_db
from app import celery, db

from src.client.models import Client, ClientArchetype, ClientSDR
from src.ml.models import TextGeneration
from src.prospecting.models import Prospect, ProspectStatus, ProspectOverallStatus, ProspectStatusRecords
from src.research.models import (
    AccountResearchPoints,
    ResearchPayload,
    ResearchPoints,
    ResearchType,
    IScraperPayloadCache,
    IScraperPayloadType,
)
from src.research.website.serp_news_extractor_transformer import (
    SerpNewsExtractorTransformer,
)
from src.research.services import create_iscraper_payload_cache
from src.simulation.models import Simulation, SimulationRecord
from src.utils.abstract.attr_utils import deep_get
from src.utils.converters.string_converters import clean_company_name
from src.voice_builder.models import VoiceBuilderSamples
from ..sample_research_response import SAMPLE_RESEARCH_RESPONSE

import json
import yaml
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

    return yaml.safe_load(response.text)


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


@celery.task
def get_research_payload_new(prospect_id: int, test_mode: bool = False):
    from src.prospecting.services import (
        get_linkedin_slug_from_url,
        get_navigator_slug_from_url,
    )
    from src.prospecting.models import Prospect

    if test_mode:
        return SAMPLE_RESEARCH_RESPONSE

    p: Prospect = Prospect.query.get(prospect_id)
    rp: ResearchPayload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).order_by(ResearchPayload.created_at.desc()).first()
    if rp and p.company_id and rp.created_at > (datetime.now() - timedelta(weeks=2)):
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

        # Add to cache if the payload is valid
        if deep_get(personal_info, "first_name") is not None:
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
        datetime.now() - timedelta(weeks=10)
    ):
        company_info = json.loads(iscraper_company_cache.payload)
        add_company_cache_to_db(company_info)
    elif company_url:
        # Get iScraper payload
        # delimeter is whatever is after the .com/ in company_url
        company_info = {}
        try:
            company_slug = company_url.split(".com/")[1].split("/")[1]
            company_info = research_corporate_profile_details(company_name=company_slug)
        except:
            pass

        # Add to cache if the payload is valid
        if deep_get(company_info, "details.name") is not None:
            create_iscraper_payload_cache(
                linkedin_url=company_url,
                payload=company_info,
                payload_type=IScraperPayloadType.COMPANY,
            )
            add_company_cache_to_db(company_info)

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
    elif deep_get(payload, "first_name") or deep_get(
        payload, "details.name"
    ):  # first_name present in personal payload, details.name present in company payload
        raise ValueError("No error in payload")

    message = deep_get(payload, "message")
    if message:
        return message

    detail = deep_get(payload, "detail")
    if detail:
        return detail

    return "iScraper error not provided"


@celery.task
def get_research_and_bullet_points_new(prospect_id: int, test_mode: bool):
    from src.research.generate_research import generate_research_points

    return generate_research_points(prospect_id=prospect_id, test_mode=test_mode)

@celery.task
def check_and_apply_do_not_contact(client_sdr_id: int, prospect_id: int):

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)

    def is_on_dnc_list(prospect, client, client_sdr):
        # Check against Client's DNC lists
        def is_on_dnc_list_helper(dnc_list, prospect_attr, exact_match=False):
            # lowercase everything for case-insensitive matching
            if not dnc_list or not prospect_attr:
                return False
            prospect_attr_lower = prospect_attr.lower()
            if exact_match:
                return prospect_attr_lower in (item.lower() for item in dnc_list)
            
            return any(item.lower() in prospect_attr_lower for item in dnc_list)

        if (
            is_on_dnc_list_helper(client.do_not_contact_company_names, prospect.company, exact_match=True) or
            is_on_dnc_list_helper(client.do_not_contact_keywords_in_company_names, prospect.company) or
            is_on_dnc_list_helper(client.do_not_contact_industries, prospect.industry) or
            is_on_dnc_list_helper(client.do_not_contact_location_keywords, prospect.company_location) or
            is_on_dnc_list_helper(client.do_not_contact_titles, prospect.title, exact_match=True) or
            is_on_dnc_list_helper(client.do_not_contact_prospect_location_keywords, prospect.prospect_location, exact_match=True) or
            is_on_dnc_list_helper(client.do_not_contact_people_names, prospect.full_name, exact_match=True) or
            is_on_dnc_list_helper(client.do_not_contact_emails, prospect.email, exact_match=True)
        ):
            return True

        if (
            is_on_dnc_list_helper(client_sdr.do_not_contact_company_names, prospect.company, exact_match=True) or
            is_on_dnc_list_helper(client_sdr.do_not_contact_keywords_in_company_names, prospect.company) or
            is_on_dnc_list_helper(client_sdr.do_not_contact_industries, prospect.industry, exact_match=True) or
            is_on_dnc_list_helper(client_sdr.do_not_contact_location_keywords, prospect.company_location) or
            is_on_dnc_list_helper(client_sdr.do_not_contact_titles, prospect.title, exact_match=True) or
            is_on_dnc_list_helper(client_sdr.do_not_contact_prospect_location_keywords, prospect.prospect_location) or
            is_on_dnc_list_helper(client_sdr.do_not_contact_people_names, prospect.full_name, exact_match=True) or
            is_on_dnc_list_helper(client_sdr.do_not_contact_emails, prospect.email, exact_match=True)
        ):
            return True
        return False

    if is_on_dnc_list(prospect, client, client_sdr):
        prospect.status = ProspectStatus.NOT_QUALIFIED
        prospect.overall_status = ProspectOverallStatus.REMOVED
        db.session.add(prospect)
        db.session.commit()
    else:
        prospect.status = ProspectStatus.PROSPECTED
        db.session.add(prospect)
        db.session.commit()


def reset_prospect_approved_status(prospect_id: int):
    p: Prospect = Prospect.query.get(prospect_id)

    p.approved_outreach_message_id = None
    p.overall_status = ProspectOverallStatus.PROSPECTED
    p.status = ProspectStatus.PROSPECTED
    db.session.add(p)
    db.session.commit()

    prospect_status_records: ProspectStatusRecords = ProspectStatusRecords.query.filter(
        ProspectStatusRecords.prospect_id == prospect_id
    ).all()
    for psr in prospect_status_records:
        db.session.delete(psr)
        db.session.commit()

    return True


def delete_research_points_and_payload_by_prospect_id(prospect_id: int):
    research_payloads = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).all()

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

    account_research_point: list = AccountResearchPoints.query.filter(
        AccountResearchPoints.prospect_id == prospect_id
    ).all()

    for arp in account_research_point:
        db.session.delete(arp)
        db.session.commit()

    simulations: list = Simulation.query.filter(
        Simulation.prospect_id == prospect_id
    ).all()
    for simulation in simulations:
        simulation_id = simulation.id
        simulation_records = SimulationRecord.query.filter(
            SimulationRecord.simulation_id == simulation_id
        ).all()
        for simulation_record in simulation_records:
            db.session.delete(simulation_record)
            db.session.commit()

        db.session.delete(simulation)
        db.session.commit()

    voice_builder_samples = VoiceBuilderSamples.query.filter(
        VoiceBuilderSamples.prospect_id == prospect_id
    ).all()
    for voice_builder_sample in voice_builder_samples:
        db.session.delete(voice_builder_sample)
        db.session.commit()

    text_generations: TextGeneration = TextGeneration.query.filter(
        TextGeneration.prospect_id == prospect_id
    ).all()
    for text_generation in text_generations:
        db.session.delete(text_generation)
        db.session.commit()


@celery.task
def reset_prospect_research_and_messages(prospect_id: int, hard_reset: bool = False):
    from src.message_generation.services import delete_message_generation_by_prospect_id

    reset_prospect_approved_status(prospect_id=prospect_id)
    delete_message_generation_by_prospect_id(prospect_id=prospect_id)
    if hard_reset:
        delete_research_points_and_payload_by_prospect_id(prospect_id=prospect_id)


def reset_batch_of_prospect_research_and_messages(
    prospect_ids: list, use_celery: Optional[bool] = True
):
    for p_id in prospect_ids:
        if use_celery:
            reset_prospect_research_and_messages.delay(prospect_id=p_id)
        else:
            reset_prospect_research_and_messages(prospect_id=p_id)
