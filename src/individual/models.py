from src.company.models import Company
from app import db

class Individual(db.Model):
    __tablename__ = "individual"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)

    # Self-proclaimed title
    title = db.Column(db.String, nullable=True)

    bio = db.Column(db.String, nullable=True)

    linkedin_url = db.Column(db.String, nullable=True)
    instagram_url = db.Column(db.String, nullable=True)
    facebook_url = db.Column(db.String, nullable=True)
    twitter_url = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True, index=True, unique=True)
    phone = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)

    li_public_id = db.Column(db.String, nullable=True, index=True, unique=True)
    li_urn_id = db.Column(db.String, nullable=True, index=True, unique=True)

    img_url = db.Column(db.String, nullable=True)
    img_expire = db.Column(db.Numeric(20, 0), nullable=False, default=0)

    industry = db.Column(db.String, nullable=True)

    # For most recent job
    company_name = db.Column(db.String, nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True)

    linkedin_connections = db.Column(db.Integer, nullable=True)
    linkedin_recommendations = db.Column(db.ARRAY(db.JSON), nullable=True)

    linkedin_followers = db.Column(db.Integer, nullable=True)
    instagram_followers = db.Column(db.Integer, nullable=True)
    facebook_followers = db.Column(db.Integer, nullable=True)
    twitter_followers = db.Column(db.Integer, nullable=True)

    birth_date = db.Column(db.Date, nullable=True)
    location = db.Column(db.JSON, nullable=True)

    language_country = db.Column(db.String, nullable=True)
    language_locale = db.Column(db.String, nullable=True)

    skills = db.Column(db.ARRAY(db.String), nullable=True)
    websites = db.Column(db.ARRAY(db.JSON), nullable=True)

    recent_education_school = db.Column(db.String, nullable=True)
    recent_education_degree = db.Column(db.String, nullable=True)
    recent_education_field = db.Column(db.String, nullable=True)
    recent_education_start_date = db.Column(db.Date, nullable=True)
    recent_education_end_date = db.Column(db.Date, nullable=True)

    recent_job_title = db.Column(db.String, nullable=True)
    # For recent job company, see company_name and company_id
    recent_job_start_date = db.Column(db.Date, nullable=True)
    recent_job_end_date = db.Column(db.Date, nullable=True)
    recent_job_description = db.Column(db.String, nullable=True)
    recent_job_location = db.Column(db.JSON, nullable=True)

    education_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    patent_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    award_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    certification_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    organization_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    project_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    publication_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    course_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    test_score_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    work_history = db.Column(db.ARRAY(db.JSON), nullable=True)
    volunteer_history = db.Column(db.ARRAY(db.JSON), nullable=True)

    linkedin_similar_profiles = db.Column(db.ARRAY(db.JSON), nullable=True)

    def to_dict(self):
        
        if self.company_id:
            company: Company = Company.query.get(self.company_id)
            company_data = company.to_dict()
        else:
            company_data = None

        return {
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "title": self.title,
            "bio": self.bio,
            "linkedin_url": self.linkedin_url,
            "instagram_url": self.instagram_url,
            "facebook_url": self.facebook_url,
            "twitter_url": self.twitter_url,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "li_public_id": self.li_public_id,
            "li_urn_id": self.li_urn_id,
            "img_url": self.img_url,
            "img_expire": self.img_expire,
            "industry": self.industry,
            "company": company_data,
            "followers": {
                "linkedin": self.linkedin_followers,
                "instagram": self.instagram_followers,
                "facebook": self.facebook_followers,
                "twitter": self.twitter_followers,
            },
            "birth_date": self.birth_date,
            "location": self.location,
            "language": {
                "country": self.language_country,
                "locale": self.language_locale,
            },
            "skills": self.skills,
            "websites": self.websites,
            "education": {
                "recent_school": self.recent_education_school,
                "recent_degree": self.recent_education_degree,
                "recent_field": self.recent_education_field,
                "recent_start_date": self.recent_education_start_date,
                "recent_end_date": self.recent_education_end_date,
                "history": self.education_history,
            },
            "patents": self.patent_history,
            "awards": self.award_history,
            "certifications": self.certification_history,
            "organizations": self.organization_history,
            "projects": self.project_history,
            "publications": self.publication_history,
            "courses": self.course_history,
            "test_scores": self.test_score_history,
            "work": {
                "recent_title": self.recent_job_title,
                "recent_company": self.company_name,
                "recent_start_date": self.recent_job_start_date,
                "recent_end_date": self.recent_job_end_date,
                "recent_description": self.recent_job_description,
                "recent_location": self.recent_job_location,
                "history": self.work_history,
            },
            "volunteer": self.volunteer_history,
            "similar_profiles": self.linkedin_similar_profiles,
        }


class IndividualsUpload(db.Model):
    __tablename__ = "individuals_upload"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    total_size = db.Column(db.Integer, nullable=False)
    upload_size = db.Column(db.Integer, nullable=False)
    payload_data = db.Column(db.ARRAY(db.JSON), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "total_size": self.total_size,
            "upload_size": self.upload_size,
            "payload_data": self.payload_data,
            "created_at": self.created_at,
        }
