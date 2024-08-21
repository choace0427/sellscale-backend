from typing import Optional

from app import db
from sqlalchemy.dialects.postgresql import JSONB

import enum


class ResearchType(enum.Enum):
    LINKEDIN_ISCRAPER = "LINKEDIN_ISCRAPER"
    SERP_PAYLOAD = "SERP_PAYLOAD"
    SDR_QUESTIONNAIRE = "SDR_QUESTIONNAIRE"
    CUSTOM_DATA = "CUSTOM_DATA"
    AI_QUESTION_DATA = "AI_QUESTION_DATA"


class AccountResearchType(enum.Enum):
    GENERIC_RESEARCH = "GENERIC_RESEARCH"
    CHATGPT_CHAIN_RESEARCH = "CHATGPT_CHAIN_RESEARCH"


# class ResearchPointType(enum.Enum):
#     CURRENT_JOB_DESCRIPTION = (
#         "CURRENT_JOB_DESCRIPTION"  # Description of Current Company
#     )
#     CURRENT_JOB_SPECIALTIES = "CURRENT_JOB_SPECIALTIES"
#     CURRENT_JOB_INDUSTRY = "CURRENT_JOB_INDUSTRY"
#     CURRENT_EXPERIENCE_DESCRIPTION = "CURRENT_EXPERIENCE_DESCRIPTION"
#     LINKEDIN_BIO_SUMMARY = "LINKEDIN_BIO_SUMMARY"
#     YEARS_OF_EXPERIENCE = "YEARS_OF_EXPERIENCE"
#     CURRENT_LOCATION = "CURRENT_LOCATION"
#     YEARS_OF_EXPERIENCE_AT_CURRENT_JOB = "YEARS_OF_EXPERIENCE_AT_CURRENT_JOB"
#     LIST_OF_PAST_JOBS = "LIST_OF_PAST_JOBS"
#     RECENT_PATENTS = "RECENT_PATENTS"
#     RECENT_RECOMMENDATIONS = "RECENT_RECOMMENDATIONS"
#     GENERAL_WEBSITE_TRANSFORMER = "GENERAL_WEBSITE_TRANSFORMER"

#     COMMON_EDUCATION = "COMMON_EDUCATION"

#     SERP_NEWS_SUMMARY = "SERP_NEWS_SUMMARY"  # Positive sumamry of recent news
#     SERP_NEWS_SUMMARY_NEGATIVE = (
#         "SERP_NEWS_SUMMARY_NEGATIVE"  # Negative summary of recent news
#     )

#     CUSTOM = "CUSTOM"

#     # EXPERIENCE = "EXPERIENCE"
#     # CURRENT_JOB = "CURRENT_JOB"
#     # PROJECT = "PROJECT"
#     # RECOMMENDATION = "RECOMMENDATION"

#     @classmethod
#     def has_value(cls, value):
#         return value in cls._value2member_map_


class ResearchPayload(db.Model):
    __tablename__ = "research_payload"

    id = db.Column(db.Integer, primary_key=True)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    research_type = db.Column(db.Enum(ResearchType), nullable=False)
    research_sub_type = db.Column(db.String, nullable=True)
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


class ResearchPointType(db.Model):
    __tablename__ = "research_point_type"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=False)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)
    function_name = db.Column(db.String, nullable=False)

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    category = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "client_sdr_id": self.client_sdr_id,
            "client_id": self.client_id,
            "function_name": self.function_name,
            "archetype_id": self.archetype_id,
            "category": self.category,
        }

    def get_allowedlist_from_blocklist(blocklist: list[str]) -> list[str]:
        allowedlist: list[ResearchPointType] = ResearchPointType.query.filter(
            ResearchPointType.name.notin_(blocklist),
            ResearchPointType.active.is_(True),
            ResearchPointType.client_sdr_id.is_(None),
            ResearchPointType.client_id.is_(None),
        ).all()

        return [a.name for a in allowedlist]


class ResearchPoints(db.Model):
    __tablename__ = "research_point"

    id = db.Column(db.Integer, primary_key=True)

    research_payload_id = db.Column(db.Integer, db.ForeignKey("research_payload.id"))
    research_point_type = db.Column(db.String, nullable=False)
    value = db.Column(db.String, nullable=False)

    flagged = db.Column(db.Boolean, nullable=True)

    research_point_metadata = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "research_payload_id": self.research_payload_id,
            "research_point_type": self.research_point_type,
            "value": self.value,
            "flagged": self.flagged,
            "research_point_metadata": self.research_point_metadata,
        }

    def get_by_payload_id(payload_id: int) -> list:
        return ResearchPoints.query.filter_by(research_payload_id=payload_id).all()

    def get_research_points_by_prospect_id(
        prospect_id: int,
        bump_framework_id: Optional[int] = None,
        bump_framework_template_id: Optional[int] = None,
        email_sequence_step_id: Optional[int] = None,
        email_reply_framework_id: Optional[int] = None,
    ) -> list:
        from model_import import ClientArchetype, Prospect
        from src.bump_framework.models import BumpFramework, BumpFrameworkTemplates

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

        # Filter out points that are in the bump framework template blocklist
        if bump_framework_template_id:
            bump_framework_template: BumpFrameworkTemplates = (
                BumpFrameworkTemplates.query.get(bump_framework_template_id)
            )
            if (
                bump_framework_template
                and bump_framework_template.transformer_blocklist
            ):
                research_points = [
                    p
                    for p in research_points
                    if p.research_point_type
                    not in bump_framework_template.transformer_blocklist
                ]

        # Filter out points that are in the email sequence step blocklist
        if email_sequence_step_id:
            from src.email_sequencing.models import EmailSequenceStep

            email_sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(
                email_sequence_step_id
            )
            if email_sequence_step and email_sequence_step.transformer_blocklist:
                research_points = [
                    p
                    for p in research_points
                    if p.research_point_type
                    not in email_sequence_step.transformer_blocklist
                ]

        # Filter out points that are in the email reply framework blocklist
        if email_reply_framework_id:
            from src.email_replies.models import EmailReplyFramework

            email_reply_framework: EmailReplyFramework = EmailReplyFramework.query.get(
                email_reply_framework_id
            )
            if email_reply_framework and email_reply_framework.research_blocklist:
                research_points = [
                    p
                    for p in research_points
                    if p.research_point_type
                    not in email_reply_framework.research_blocklist
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


class WebsiteMetadataCache(db.Model):
    __tablename__ = "website_metadata_cache"

    id = db.Column(db.Integer, primary_key=True)

    website_url = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    summary = db.Column(db.String, nullable=False)
    products = db.Column(db.ARRAY(db.String), nullable=False)
    industries = db.Column(db.ARRAY(db.String), nullable=False)
    target_profiles = db.Column(db.ARRAY(db.String), nullable=False)
    company_type = db.Column(db.String, nullable=False)
    location = db.Column(db.String, nullable=False)
    highlights = db.Column(db.ARRAY(db.String), nullable=False)
    linkedin_url = db.Column(db.String, nullable=False)
    twitter_url = db.Column(db.String, nullable=False)
    crunchbase_url = db.Column(db.String, nullable=False)
    instagram_url = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    address = db.Column(db.String, nullable=False)

    company_name = db.Column(db.String, nullable=True)
    mission = db.Column(db.String, nullable=True)
    value_proposition = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "website_url": self.website_url,
            "description": self.description,
            "summary": self.summary,
            "products": self.products,
            "industries": self.industries,
            "target_profiles": self.target_profiles,
            "company_type": self.company_type,
            "location": self.location,
            "highlights": self.highlights,
            "linkedin_url": self.linkedin_url,
            "twitter_url": self.twitter_url,
            "crunchbase_url": self.crunchbase_url,
            "instagram_url": self.instagram_url,
            "email": self.email,
            "address": self.address,
            "company_name": self.company_name,
            "mission": self.mission,
            "value_proposition": self.value_proposition,
        }
