from app import db
from sqlalchemy.orm import relationship


class Individual(db.Model):
    __tablename__ = "individual"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    bio = db.Column(db.String, nullable=True)

    linkedin_url = db.Column(db.String, nullable=True, unique=True)
    instagram_url = db.Column(db.String, nullable=True)
    facebook_url = db.Column(db.String, nullable=True)
    twitter_url = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True, unique=True)
    phone = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)

    li_urn_id = db.Column(db.String, nullable=True)

    img_url = db.Column(db.String, nullable=True)
    img_expire = db.Column(db.Numeric(20, 0), nullable=False, default=0)

    industry = db.Column(db.String, nullable=True)
    company_name = db.Column(db.String, nullable=True)
    company_url = db.Column(db.String, nullable=True)
    company_size = db.Column(db.String, nullable=True)
    company_description = db.Column(db.String, nullable=True)

    linkedin_followers = db.Column(db.Integer, nullable=True)
    instagram_followers = db.Column(db.Integer, nullable=True)
    facebook_followers = db.Column(db.Integer, nullable=True)
    twitter_followers = db.Column(db.Integer, nullable=True)

    # TODO: Maybe include a birthday field? We do get that li data

    # ref to campaigns
    # prospects = relationship("Prospect", backref="individual")

    def to_dict(self):
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
            "li_urn_id": self.li_urn_id,
            "img_url": self.img_url,
            "img_expire": self.img_expire,
            "industry": self.industry,
            "company": {
                "name": self.company_name,
                "url": self.company_url,
                "size": self.company_size,
                "description": self.company_description,
            },
            "followers": {
                "linkedin": self.linkedin_followers,
                "instagram": self.instagram_followers,
                "facebook": self.facebook_followers,
                "twitter": self.twitter_followers,
            },
        }
