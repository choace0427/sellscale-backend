from typing import Optional

from app import db
from sqlalchemy.dialects.postgresql import JSONB

import enum


class ResearchType(enum.Enum):
    LINKEDIN_ISCRAPER = "LINKEDIN_ISCRAPER"
    SERP_PAYLOAD = "SERP_PAYLOAD"
    SDR_QUESTIONNAIRE = "SDR_QUESTIONNAIRE"


class AccountResearchType(enum.Enum):
    GENERIC_RESEARCH = "GENERIC_RESEARCH"
    CHATGPT_CHAIN_RESEARCH = "CHATGPT_CHAIN_RESEARCH"


class ResearchPointType(enum.Enum):
    CURRENT_JOB_DESCRIPTION = (
        "CURRENT_JOB_DESCRIPTION"  # Description of Current Company
    )
    CURRENT_JOB_SPECIALTIES = "CURRENT_JOB_SPECIALTIES"
    CURRENT_EXPERIENCE_DESCRIPTION = "CURRENT_EXPERIENCE_DESCRIPTION"
    LINKEDIN_BIO_SUMMARY = "LINKEDIN_BIO_SUMMARY"
    YEARS_OF_EXPERIENCE = "YEARS_OF_EXPERIENCE"
    YEARS_OF_EXPERIENCE_AT_CURRENT_JOB = "YEARS_OF_EXPERIENCE_AT_CURRENT_JOB"
    LIST_OF_PAST_JOBS = "LIST_OF_PAST_JOBS"
    RECENT_PATENTS = "RECENT_PATENTS"
    RECENT_RECOMMENDATIONS = "RECENT_RECOMMENDATIONS"
    GENERAL_WEBSITE_TRANSFORMER = "GENERAL_WEBSITE_TRANSFORMER"

    COMMON_EDUCATION = "COMMON_EDUCATION"

    SERP_NEWS_SUMMARY = "SERP_NEWS_SUMMARY"  # Positive sumamry of recent news
    SERP_NEWS_SUMMARY_NEGATIVE = (
        "SERP_NEWS_SUMMARY_NEGATIVE"  # Negative summary of recent news
    )

    CUSTOM = "CUSTOM"

    # EXPERIENCE = "EXPERIENCE"
    # CURRENT_JOB = "CURRENT_JOB"
    # PROJECT = "PROJECT"
    # RECOMMENDATION = "RECOMMENDATION"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class ResearchPayload(db.Model):
    __tablename__ = "research_payload"

    id = db.Column(db.Integer, primary_key=True)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    research_type = db.Column(db.Enum(ResearchType), nullable=False)
    payload = db.Column(db.JSON, nullable=False)

    def get_by_id(id):
        return ResearchPayload.query.filter_by(id=id).first()

    def get_by_prospect_id(prospect_id: int, payload_type: ResearchType):
        rp = ResearchPayload.query.filter_by(
            prospect_id=prospect_id, research_type=payload_type
        ).first()
        if not rp:
            return None

        return rp


class ResearchPoints(db.Model):
    __tablename__ = "research_point"

    id = db.Column(db.Integer, primary_key=True)

    research_payload_id = db.Column(db.Integer, db.ForeignKey("research_payload.id"))
    research_point_type = db.Column(db.Enum(ResearchPointType), nullable=False)
    value = db.Column(db.String, nullable=False)

    flagged = db.Column(db.Boolean, nullable=True)

    research_point_metadata = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "research_payload_id": self.research_payload_id,
            "research_point_type": self.research_point_type.value,
            "value": self.value,
            "flagged": self.flagged,
            "research_point_metadata": self.research_point_metadata,
        }

    def get_by_payload_id(payload_id: int) -> list:
        return ResearchPoints.query.filter_by(research_payload_id=payload_id).all()

    def get_research_points_by_prospect_id(
        prospect_id: int, bump_framework_id: Optional[int] = None
    ) -> list:
        from model_import import ClientArchetype, Prospect
        from src.bump_framework.models import BumpFramework

        prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        if not prospect:
            return []
        client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
            id=prospect.archetype_id
        ).first()
        transformer_blocklist = client_archetype.transformer_blocklist

        research_payloads = ResearchPayload.query.filter_by(
            prospect_id=prospect_id
        ).all()
        research_points: list[ResearchPoints] = []
        for payload in research_payloads:
            research_points.extend(
                ResearchPoints.query.filter_by(research_payload_id=payload.id).all()
            )

        # Filter out points that are in the bump framework blocklist
        if bump_framework_id:
            bump_framework: BumpFramework = BumpFramework.query.get(bump_framework_id)
            if bump_framework and bump_framework.transformer_blocklist:
                research_points = [
                    p
                    for p in research_points
                    if p.research_point_type not in bump_framework.transformer_blocklist
                ]

        # Filter out points that are in the archetype blocklist
        if not transformer_blocklist:
            return research_points

        research_points = [
            point
            for point in research_points
            if point.research_point_type not in transformer_blocklist
        ]

        return research_points


class IScraperPayloadType(enum.Enum):
    """Different types of iScraper Payloads

    PERSONAL: Payloads that are scraped from a personal LinkedIn profile
    COMPANY: Payloads that are scraped from a company LinkedIn profile

    Typically there will be a PERSONAL payload and a COMPANY payload for each Prospect
    """

    PERSONAL = "PERSONAL"
    COMPANY = "COMPANY"


class IScraperPayloadCache(db.Model):
    __tablename__ = "iscraper_payload_cache"

    id = db.Column(db.Integer, primary_key=True)
    linkedin_url = db.Column(db.String, nullable=False)
    payload = db.Column(JSONB, nullable=False)
    payload_type = db.Column(db.Enum(IScraperPayloadType), nullable=False)

    def get_iscraper_payload_cache_by_linkedin_url(linkedin_url: str):
        return (
            IScraperPayloadCache.query.filter_by(linkedin_url=linkedin_url)
            .order_by(IScraperPayloadCache.created_at.desc())
            .first()
        )


class AccountResearchPoints(db.Model):
    __tablename__ = "account_research_point"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    account_research_type = db.Column(db.Enum(AccountResearchType), nullable=False)
    title = db.Column(db.String, nullable=False)
    reason = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "account_research_type": self.account_research_type.value,
            "title": self.title,
            "reason": self.reason,
        }
