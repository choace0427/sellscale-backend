from typing import Optional
from app import db
from app import db, celery
from model_import import (
    ResearchPayload,
    ResearchPoints,
    ResearchType,
    ClientSDR,
    Prospect,
    ClientArchetype,
)
from src.research.models import (
    IScraperPayloadCache,
    IScraperPayloadType,
    ResearchPointType,
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
    prospect_id: int,
    research_type: ResearchType,
    payload: dict,
    sub_type: Optional[str] = None,
):
    """Creates a research payload"""
    payload = ResearchPayload(
        prospect_id=prospect_id,
        research_type=research_type,
        research_sub_type=(
            convert_to_research_point_type_name(sub_type) if sub_type else None
        ),
        payload=payload,
    )
    db.session.add(payload)
    db.session.commit()

    return payload.id


def create_research_point(
    payload_id: int,
    research_point_type: str,
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
    category: str,
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

            create_custom_research_point_type.delay(
                prospect_id,
                label,
                {"custom": value},
                category,
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task
def create_custom_research_point_type(
    prospect_id: int, label: str, data: dict, category: Optional[str] = None
) -> list[int]:
    """Creates a custom research point"""

    payload_id = create_research_payload(
        prospect_id, ResearchType.CUSTOM_DATA, data, sub_type=label
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    value = create_research_point_type(
        name=label,
        description="Custom research point",
        client_sdr_id=prospect.client_sdr_id,
        function_name="get_custom_research",
        archetype_id=prospect.archetype_id,
        category=category,
    )

    from src.research.generate_research import generate_research_points

    generate_research_points(
        prospect_id=prospect_id,
    )

    return value


def flag_research_point(research_point_id: int):
    """Flags a research point"""
    rp: ResearchPoints = ResearchPoints.query.get(research_point_id)
    if not rp:
        raise Exception("Research point not found")
    rp.flagged = True
    db.session.add(rp)
    db.session.commit()

    return True


def create_research_point_type(
    name: str,
    description: str,
    client_sdr_id: int,
    function_name: str,
    category: Optional[str] = None,
    archetype_id: Optional[int] = None,
):
    """Creates a research point type"""
    name = convert_to_research_point_type_name(name)

    # Check if the research point type already exists for this client
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    existing_rpt: ResearchPointType = ResearchPointType.query.filter(
        ResearchPointType.name == name,
        ResearchPointType.client_id == client_sdr.client_id,
    ).first()
    if existing_rpt:
        return existing_rpt.id

    research_point_type = ResearchPointType(
        name=name,
        description=description,
        active=True,
        client_sdr_id=client_sdr_id,
        client_id=client_sdr.client_id,
        function_name=function_name,
        archetype_id=archetype_id,
        category=category,
    )
    db.session.add(research_point_type)
    db.session.commit()

    return research_point_type.id


def get_all_research_point_types(
    client_sdr_id: Optional[int] = None,
    names_only=False,
    archetype_id: Optional[int] = None,
):
    # Get all generic research point types (no client id) and client specific research point types
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    research_point_types: list[ResearchPointType] = ResearchPointType.query.filter(
        ResearchPointType.active.is_(True),
        db.or_(
            ResearchPointType.client_id.is_(None),
            ResearchPointType.client_id == client_sdr.client_id if client_sdr else None,
        ),
    ).all()

    def filter_rpt(rpt: ResearchPointType):
        if rpt.category == "CLIENT" or rpt.category is None:
            return True
        elif rpt.category == "ARCHETYPE":
            return rpt.archetype_id == archetype_id
        elif rpt.category == "SDR":
            return rpt.client_sdr_id == client_sdr_id
        else:
            return False

    research_point_types = [
        research_point_type
        for research_point_type in research_point_types
        if filter_rpt(research_point_type)
    ]

    if names_only:
        return [rpt.name for rpt in research_point_types]
    else:
        return [rpt.to_dict() for rpt in research_point_types]


def get_research_point_type(name: str):
    research_point_type: ResearchPointType = ResearchPointType.query.filter(
        ResearchPointType.name == name
    ).first()
    return research_point_type.to_dict() if research_point_type else None


def convert_to_research_point_type_name(name: str):
    # Replace all non-alphanumeric characters with underscores
    return "".join([c if c.isalnum() else "_" for c in name]).upper()


def execute_research_point_type_function(type_name: str):
    research_point_type = get_research_point_type(type_name)

    # return [
    #     {
    #         "transformer": ResearchPointType.CURRENT_JOB_SPECIALTIES.value,
    #         "description": "Extracts the specialties of the current job",
    #         "example": "Filene Research Institute is a research, innovation, applied services, and credit unions",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.CURRENT_JOB_DESCRIPTION.value,
    #         "description": "Extracts the description of the current job",
    #         "example": "Filene Research Institute is research and incubation lab helping to advance credit unions and other cooperative financial products \\& services",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.CURRENT_JOB_INDUSTRY.value,
    #         "description": "Extracts the industry of the current job",
    #         "example": "The Coca-Cola Company works in the Food & Beverages industry",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.CURRENT_EXPERIENCE_DESCRIPTION.value,
    #         "description": "Extracts the description of the current experience",
    #         "example": "Founder of The Volta Group, an automotive coaching and training firm, focusing on sales growth and customer experience optimization",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.YEARS_OF_EXPERIENCE.value,
    #         "description": "Extracts the years of experience",
    #         "example": "14+ years of experience in industry",
    #         "deprecated": True,
    #     },
    #     {
    #         "transformer": ResearchPointType.YEARS_OF_EXPERIENCE_AT_CURRENT_JOB.value,
    #         "description": "Extracts the years of experience at current job",
    #         "example": "Spent 6 years at The Volta Group",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.LIST_OF_PAST_JOBS.value,
    #         "description": "Extracts the list of past jobs",
    #         "example": "Saw that they've worked at Cordero Consulting and Associates in the past",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.CURRENT_LOCATION.value,
    #         "description": "Extracts the current location",
    #         "example": "David Wei is based in San Francisco, California",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.RECENT_PATENTS.value,
    #         "description": "Extracts the recent patents",
    #         "example": "Noticed that you've patented 'point-to-point secured relay system enterprise architecture design', that's so interesting!",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.RECENT_RECOMMENDATIONS.value,
    #         "description": "Extracts the recent recommendations",
    #         "example": "Saw the note Yvonne left for you. Looks like they love how you run a professional, timely and friendly team and that you deliver exceptional quality results!",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.GENERAL_WEBSITE_TRANSFORMER.value,
    #         "description": "Extracts the general website transformer",
    #         "example": "I saw your website and the Small Miracles Academy and was wondering why parents are sending their children there",
    #         "deprecated": True,
    #     },
    #     {
    #         "transformer": ResearchPointType.SERP_NEWS_SUMMARY.value,
    #         "description": "Extracts the SERP news summary",
    #         "example": "Saw the article on TechCrunch about your company",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.SERP_NEWS_SUMMARY_NEGATIVE.value,
    #         "description": "Extracts the negative SERP news summary",
    #         "example": "Saw the article on TechCrunch about your company losing $1M in funding to a competitor",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.LINKEDIN_BIO_SUMMARY.value,
    #         "description": "Extracts the linkedin bio and creates a summary using OpenAI",
    #         "example": "David Wei is passionate about distributed systems and highly scalable infrastructure.",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.COMMON_EDUCATION.value,
    #         "description": "Extracts the common education",
    #         "example": "John Doe attended University of California, Berkeley. I attended University of California, Berkeley from 2016 to 2020.",
    #         "deprecated": False,
    #     },
    #     {
    #         "transformer": ResearchPointType.CUSTOM.value,
    #         "description": "Used to create custom research points",
    #         "example": "{ 'label': 'Favorite Food', 'value': 'Pizza' }",
    #         "deprecated": False,
    #     },
    # ]


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
