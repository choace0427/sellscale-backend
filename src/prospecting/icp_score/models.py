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

    def to_dict(self):
        return {
            "client_archetype_id": self.client_archetype_id,
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
        }
