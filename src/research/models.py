from app import db
import enum


class ResearchType(enum.Enum):
    LINKEDIN_ISCRAPER = "LINKEDIN_ISCRAPER"
    SERP_PAYLOAD = "SERP_PAYLOAD"


class ResearchPointType(enum.Enum):
    CURRENT_JOB_DESCRIPTION = "CURRENT_JOB_DESCRIPTION"
    CURRENT_JOB_SPECIALTIES = "CURRENT_JOB_SPECIALTIES"
    CURRENT_EXPERIENCE_DESCRIPTION = "CURRENT_EXPERIENCE_DESCRIPTION"
    YEARS_OF_EXPERIENCE = "YEARS_OF_EXPERIENCE"
    YEARS_OF_EXPERIENCE_AT_CURRENT_JOB = "YEARS_OF_EXPERIENCE_AT_CURRENT_JOB"
    LIST_OF_PAST_JOBS = "LIST_OF_PAST_JOBS"
    RECENT_PATENTS = "RECENT_PATENTS"
    RECENT_RECOMMENDATIONS = "RECENT_RECOMMENDATIONS"
    GENERAL_WEBSITE_TRANSFORMER = "GENERAL_WEBSITE_TRANSFORMER"

    SERP_NEWS_SUMMARY = "SERP_NEWS_SUMMARY"

    # EXPERIENCE = "EXPERIENCE"
    # CURRENT_JOB = "CURRENT_JOB"
    # PROJECT = "PROJECT"
    # RECOMMENDATION = "RECOMMENDATION"


class ResearchPayload(db.Model):
    __tablename__ = "research_payload"

    id = db.Column(db.Integer, primary_key=True)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    research_type = db.Column(db.Enum(ResearchType), nullable=False)
    payload = db.Column(db.JSON, nullable=False)

    def get_by_id(id):
        return ResearchPayload.query.filter_by(id=id).first()


class ResearchPoints(db.Model):
    __tablename__ = "research_point"

    id = db.Column(db.Integer, primary_key=True)

    research_payload_id = db.Column(db.Integer, db.ForeignKey("research_payload.id"))
    research_point_type = db.Column(db.Enum(ResearchPointType), nullable=False)
    value = db.Column(db.String, nullable=False)

    flagged = db.Column(db.Boolean, nullable=True)
