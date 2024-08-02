from app import db
import enum


class ICPScoringJobQueueStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ICPScoringJobQueue(db.Model):
    __tablename__ = "icp_scoring_job_queue"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    prospect_ids = db.Column(db.ARRAY(db.Integer), nullable=True)

    run_status = db.Column(
        db.Enum(ICPScoringJobQueueStatus),
        nullable=False,
        default=ICPScoringJobQueueStatus.PENDING.value,
    )
    error_message = db.Column(db.String, nullable=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)

    manual_trigger = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "prospect_ids": self.prospect_ids,
            "run_status": self.run_status.value,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "manual_trigger": self.manual_trigger,
        }


class ICPScoringRuleset(db.Model):
    __tablename__ = "icp_scoring_ruleset"

    id = db.Column(
        db.Integer, primary_key=True
    )

    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )

    segment_id = db.Column(
        db.Integer, db.ForeignKey("segment.id"), nullable=True
    )

    # individual related
    included_individual_title_keywords = db.Column(db.ARRAY(db.String), nullable=True)
    excluded_individual_title_keywords = db.Column(db.ARRAY(db.String), nullable=True)

    included_individual_industry_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    excluded_individual_industry_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )

    individual_years_of_experience_start = db.Column(db.Integer, nullable=True)
    individual_years_of_experience_end = db.Column(db.Integer, nullable=True)

    included_individual_skills_keywords = db.Column(db.ARRAY(db.String), nullable=True)
    excluded_individual_skills_keywords = db.Column(db.ARRAY(db.String), nullable=True)

    included_individual_locations_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    excluded_individual_locations_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )

    included_individual_generalized_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    excluded_individual_generalized_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )

    # company related
    included_company_name_keywords = db.Column(db.ARRAY(db.String), nullable=True)
    excluded_company_name_keywords = db.Column(db.ARRAY(db.String), nullable=True)

    included_company_locations_keywords = db.Column(db.ARRAY(db.String), nullable=True)
    excluded_company_locations_keywords = db.Column(db.ARRAY(db.String), nullable=True)

    company_size_start = db.Column(db.Integer, nullable=True)
    company_size_end = db.Column(db.Integer, nullable=True)

    included_company_industries_keywords = db.Column(db.ARRAY(db.String), nullable=True)
    excluded_company_industries_keywords = db.Column(db.ARRAY(db.String), nullable=True)

    included_company_generalized_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    excluded_company_generalized_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )

    included_individual_education_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    excluded_individual_education_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )

    included_individual_seniority_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    excluded_individual_seniority_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )

    hash = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_archetype_id": self.client_archetype_id,
            "segment_id": self.segment_id,
            "included_individual_title_keywords": self.included_individual_title_keywords,
            "excluded_individual_title_keywords": self.excluded_individual_title_keywords,
            "included_individual_industry_keywords": self.included_individual_industry_keywords,
            "excluded_individual_industry_keywords": self.excluded_individual_industry_keywords,
            "individual_years_of_experience_start": self.individual_years_of_experience_start,
            "individual_years_of_experience_end": self.individual_years_of_experience_end,
            "included_individual_skills_keywords": self.included_individual_skills_keywords,
            "excluded_individual_skills_keywords": self.excluded_individual_skills_keywords,
            "included_individual_locations_keywords": self.included_individual_locations_keywords,
            "excluded_individual_locations_keywords": self.excluded_individual_locations_keywords,
            "included_individual_generalized_keywords": self.included_individual_generalized_keywords,
            "excluded_individual_generalized_keywords": self.excluded_individual_generalized_keywords,
            "included_company_name_keywords": self.included_company_name_keywords,
            "excluded_company_name_keywords": self.excluded_company_name_keywords,
            "included_company_locations_keywords": self.included_company_locations_keywords,
            "excluded_company_locations_keywords": self.excluded_company_locations_keywords,
            "company_size_start": self.company_size_start,
            "company_size_end": self.company_size_end,
            "included_company_industries_keywords": self.included_company_industries_keywords,
            "excluded_company_industries_keywords": self.excluded_company_industries_keywords,
            "included_company_generalized_keywords": self.included_company_generalized_keywords,
            "excluded_company_generalized_keywords": self.excluded_company_generalized_keywords,
            "included_individual_education_keywords": self.included_individual_education_keywords,
            "excluded_individual_education_keywords": self.excluded_individual_education_keywords,
            "included_individual_seniority_keywords": self.included_individual_seniority_keywords,
            "excluded_individual_seniority_keywords": self.excluded_individual_seniority_keywords,
            "hash": self.hash,
        }
