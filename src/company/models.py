from app import db


class Company(db.Model):
    __tablename__ = "company"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String)
    universal_name = db.Column(db.String, nullable=True, index=True, unique=True)
    apollo_uuid = db.Column(db.String, nullable=True, index=True, unique=True)

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

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "universal_name": self.universal_name,
            "apollo_uuid": self.apollo_uuid,
            "type": self.type,
            "img_cover_url": self.img_cover_url,
            "img_logo_url": self.img_logo_url,
            "li_followers": self.li_followers,
            "li_company_id": self.li_company_id,
            "phone": self.phone,
            "websites": self.websites,
            "employees": self.employees,
            "founded_year": self.founded_year,
            "description": self.description,
            "specialities": self.specialities,
            "industries": self.industries,
            "locations": self.locations,
            "career_page_url": self.career_page_url,
        }


class CompanyRelation(db.Model):
    __tablename__ = "company_relation"

    id_pair = db.Column(db.Integer, primary_key=True)
    company_id_1 = db.Column(db.Integer, db.ForeignKey("company.id"))
    company_id_2 = db.Column(db.Integer, db.ForeignKey("company.id"))

    # Other relation data to go here
