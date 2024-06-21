from app import db


class ApolloCookies(db.Model):
    __tablename__ = "apollo_cookies"

    id = db.Column(db.Integer, primary_key=True)

    cookies = db.Column(db.String, nullable=False)
    csrf_token = db.Column(db.String, nullable=False)
