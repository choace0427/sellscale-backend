from app import db
import enum


class ResearchType(enum.Enum):
    LINKEDIN_ISCRAPER = "LINKEDIN_ISCRAPER"


class ResearchPointType(enum.Enum):
    EXPERIENCE = "EXPERIENCE"
    CURRENT_JOB_DESCRIPTION = "CURRENT_JOB_DESCRIPTION"
    CURRENT_JOB_SPECIALTIES = "CURRENT_JOB_SPECIALTIES"
    CURRENT_EXPERIENCE_DESCRIPTION = "CURRENT_EXPERIENCE_DESCRIPTION"
    YEARS_OF_EXPERIENCE = "YEARS_OF_EXPERIENCE"
    YEARS_OF_EXPERIENCE_AT_CURRENT_JOB = "YEARS_OF_EXPERIENCE_AT_CURRENT_JOB"
    CURRENT_JOB = "CURRENT_JOB"
    LIST_OF_PAST_JOBS = "LIST_OF_PAST_JOBS"
    RECENT_PATENTS = "RECENT_PATENTS"
    RECENT_RECOMMENDATIONS = "RECENT_RECOMMENDATIONS"
    PROJECT = "PROJECT"
    RECOMMENDATION = "RECOMMENDATION"
    GENERAL_WEBSITE_TRANSFORMER = "GENERAL_WEBSITE_TRANSFORMER"


class ResearchPayload(db.Model):
    __tablename__ = "research_payload"

    id = db.Column(db.Integer, primary_key=True)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    research_type = db.Column(db.Enum(ResearchType), nullable=False)
    payload = db.Column(db.JSON, nullable=False)


class ResearchPoints(db.Model):
    __tablename__ = "research_point"

    id = db.Column(db.Integer, primary_key=True)

    research_payload_id = db.Column(db.Integer, db.ForeignKey("research_payload.id"))
    research_point_type = db.Column(db.Enum(ResearchPointType), nullable=False)
    value = db.Column(db.String, nullable=False)
