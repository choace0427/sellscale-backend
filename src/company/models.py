
from app import db


class Company(db.Model):
    __tablename__ = "company"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String)
    universal_name = db.Column(db.String, index=True, unique=True)
    
    type = db.Column(db.String, nullable=True)

    img_cover_url = db.Column(db.String, nullable=True)
    img_logo_url = db.Column(db.String, nullable=True)

    li_followers = db.Column(db.Integer, nullable=True)
    li_company_id = db.Column(db.String, nullable=True, index=True, unique=True)

    phone = db.Column(db.String, nullable=True)
    websites = db.Column(db.ARRAY(db.String))
    employees = db.Column(db.Integer, nullable=True)

    founded_year = db.Column(db.Integer, nullable=True)

    description = db.Column(db.String, nullable=True)

    specialities = db.Column(db.ARRAY(db.String))
    industries = db.Column(db.ARRAY(db.String))
    locations = db.Column(db.ARRAY(db.JSON))

    career_page_url = db.Column(db.String, nullable=True)



class CompanyRelation(db.Model):
    __tablename__ = "company_relation"

    id_pair = db.Column(db.Integer, primary_key=True)
    company_id_1 = db.Column(db.Integer, db.ForeignKey("company.id"))
    company_id_2 = db.Column(db.Integer, db.ForeignKey("company.id"))
    
    # Other relation data to go here



