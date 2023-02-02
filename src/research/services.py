from app import db
from model_import import ResearchPayload, ResearchPoints, ResearchType
from src.research.models import ResearchPointType


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
            "transformer": ResearchPointType.LINKEDIN_BIO_SUMMARY.value,
            "description": "Extracts the linkedin bio and creates a summary using OpenAI",
            "example": "David Wei is passionate about distributed systems and highly scalable infrastructure.",
            "deprecated": False,
        },
    ]
