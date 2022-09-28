from app import db


class Prospect(db.Model):
    __tablename__ = "prospect"

    id = db.Column(db.Integer, primary_key=True)

    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    company = db.Column(db.String, nullable=True)
    company_url = db.Column(db.String, nullable=True)
    employee_count = db.Column(db.String, nullable=True)
    full_name = db.Column(db.String, nullable=True)
    industry = db.Column(db.String, nullable=True)
    linkedin_url = db.Column(db.String, nullable=True)
    linkedin_bio = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    twitter_url = db.Column(db.String, nullable=True)
