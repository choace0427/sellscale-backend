from typing import Optional
from app import db
from app import db, celery
from model_import import ResearchPayload, ResearchPoints, ResearchType
from src.research.models import (
    ResearchPointType,
    IScraperPayloadCache,
    IScraperPayloadType,
)
from sqlalchemy import text

import json


def create_iscraper_payload_cache(
    linkedin_url: str, payload: dict, payload_type: IScraperPayloadType
) -> int:
    """Creates a cache entry for a iScraper payload"""
    iscraper_payload_cache: IScraperPayloadCache = IScraperPayloadCache(
        linkedin_url=linkedin_url,
        payload=json.dumps(payload),
        payload_type=payload_type.value,
    )
    db.session.add(iscraper_payload_cache)
    db.session.commit()

    return iscraper_payload_cache.id


def create_research_payload(
    prospect_id: int, research_type: ResearchType, payload: dict
):
    """Creates a research payload"""
    payload = ResearchPayload(
        prospect_id=prospect_id, research_type=research_type, payload=payload
    )
    db.session.add(payload)
    db.session.commit()

    return payload.id


def create_research_point(
    payload_id: int,
    research_point_type: ResearchPointType,
    text: str,
    research_point_metadata: dict = None,
):
    """Creates a research point"""
    research_point = ResearchPoints(
        research_payload_id=payload_id,
        research_point_type=research_point_type,
        value=text,
        research_point_metadata=research_point_metadata,
    )
    db.session.add(research_point)
    db.session.commit()

    return research_point.id


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def run_create_custom_research_entries(
    self,
    client_sdr_id: int,
    label: str,
    entries: list[dict],
) -> bool:
    from src.prospecting.services import find_prospect_id_from_li_or_email

    try:
        for entry in entries:
            value = entry.get("value")
            if not value:
                print(f"Value not found for {entry}")
                continue

            li_url = entry.get("li_url")
            email = entry.get("email")
            prospect_id = find_prospect_id_from_li_or_email(
                client_sdr_id, li_url, email
            )
            if not prospect_id:
                print(f"Could not find prospect for {li_url} or {email}")
                continue

            research_point_ids = create_custom_research_points(
                prospect_id=prospect_id, label=label, data={"custom": value}
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def create_custom_research_points(
    prospect_id: int, label: Optional[str], data: dict
) -> list[int]:
    """Creates a custom research point"""

    payload_id = create_research_payload(prospect_id, ResearchType.CUSTOM_DATA, data)

    ids = []
    for key, value in data.items():
        research_point = ResearchPoints(
            research_payload_id=payload_id,
            research_point_type=ResearchPointType.CUSTOM,
            value=json.dumps({"label": label or key, "value": value}),
        )
        db.session.add(research_point)
        db.session.commit()
        ids.append(research_point.id)

    return ids


def flag_research_point(research_point_id: int):
    """Flags a research point"""
    rp: ResearchPoints = ResearchPoints.query.get(research_point_id)
    if not rp:
        raise Exception("Research point not found")
    rp.flagged = True
    db.session.add(rp)
    db.session.commit()

    return True


def get_all_research_point_types():
    """Returns all transformers. Payload looks like:

    return value:
    [
        {
            'transformer': CURRENT_JOB_SPECIALTIES,
            'description': 'Extracts the specialties of the current job'
            'example': 'Software Engineer, Python, Django, React, AWS',
            'deprecated' : False
        }
        ...
    ]"""

    return [
        {
            "transformer": ResearchPointType.CURRENT_JOB_SPECIALTIES.value,
            "description": "Extracts the specialties of the current job",
            "example": "Filene Research Institute is a research, innovation, applied services, and credit unions",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.CURRENT_JOB_DESCRIPTION.value,
            "description": "Extracts the description of the current job",
            "example": "Filene Research Institute is research and incubation lab helping to advance credit unions and other cooperative financial products \\& services",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.CURRENT_JOB_INDUSTRY.value,
            "description": "Extracts the industry of the current job",
            "example": "The Coca-Cola Company works in the Food & Beverages industry",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.CURRENT_EXPERIENCE_DESCRIPTION.value,
            "description": "Extracts the description of the current experience",
            "example": "Founder of The Volta Group, an automotive coaching and training firm, focusing on sales growth and customer experience optimization",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.YEARS_OF_EXPERIENCE.value,
            "description": "Extracts the years of experience",
            "example": "14+ years of experience in industry",
            "deprecated": True,
        },
        {
            "transformer": ResearchPointType.YEARS_OF_EXPERIENCE_AT_CURRENT_JOB.value,
            "description": "Extracts the years of experience at current job",
            "example": "Spent 6 years at The Volta Group",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.LIST_OF_PAST_JOBS.value,
            "description": "Extracts the list of past jobs",
            "example": "Saw that they've worked at Cordero Consulting and Associates in the past",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.CURRENT_LOCATION.value,
            "description": "Extracts the current location",
            "example": "David Wei is based in San Francisco, California",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.RECENT_PATENTS.value,
            "description": "Extracts the recent patents",
            "example": "Noticed that you've patented 'point-to-point secured relay system enterprise architecture design', that's so interesting!",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.RECENT_RECOMMENDATIONS.value,
            "description": "Extracts the recent recommendations",
            "example": "Saw the note Yvonne left for you. Looks like they love how you run a professional, timely and friendly team and that you deliver exceptional quality results!",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.GENERAL_WEBSITE_TRANSFORMER.value,
            "description": "Extracts the general website transformer",
            "example": "I saw your website and the Small Miracles Academy and was wondering why parents are sending their children there",
            "deprecated": True,
        },
        {
            "transformer": ResearchPointType.SERP_NEWS_SUMMARY.value,
            "description": "Extracts the SERP news summary",
            "example": "Saw the article on TechCrunch about your company",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.SERP_NEWS_SUMMARY_NEGATIVE.value,
            "description": "Extracts the negative SERP news summary",
            "example": "Saw the article on TechCrunch about your company losing $1M in funding to a competitor",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.LINKEDIN_BIO_SUMMARY.value,
            "description": "Extracts the linkedin bio and creates a summary using OpenAI",
            "example": "David Wei is passionate about distributed systems and highly scalable infrastructure.",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.COMMON_EDUCATION.value,
            "description": "Extracts the common education",
            "example": "John Doe attended University of California, Berkeley. I attended University of California, Berkeley from 2016 to 2020.",
            "deprecated": False,
        },
        {
            "transformer": ResearchPointType.CUSTOM.value,
            "description": "Used to create custom research points",
            "example": "{ 'label': 'Favorite Food', 'value': 'Pizza' }",
            "deprecated": False,
        },
    ]


def research_point_acceptance_rate():
    data = db.session.execute(
        text(
            """
            select 
	research_point.research_point_type,
	cast(count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') as float) / count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') "avg. acceptance %"
from generated_message
	join research_point on research_point.id = any(generated_message.research_points)
	join prospect on prospect.approved_outreach_message_id = generated_message.id
	join prospect_status_records on prospect_status_records.prospect_id = prospect.id
group by 1;
        """
        )
    ).fetchall()
    return [dict(row) for row in data]
