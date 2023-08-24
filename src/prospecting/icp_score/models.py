from app import db
import enum


class ICPScoringRuleset(db.Model):
    __tablename__ = "icp_scoring_ruleset"

    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), primary_key=True
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
