from app import db


class Echo(db.Model):
    __tablename__ = "echo"

    id = db.Column(db.Integer, primary_key=True)
