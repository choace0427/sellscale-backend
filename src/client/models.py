from app import db


class Client(db.Model):
    __tablename__ = "client"

    id = db.Column(db.Integer, primary_key=True)

    company = db.Column(db.String)
    contact_name = db.Column(db.String)
    contact_email = db.Column(db.String)


class ClientArchetype(db.Model):
    __tablename__ = "client_archetype"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    archetype = db.Column(db.String)
    filters = db.Column(db.JSON, nullable=True)
