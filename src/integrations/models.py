from app import db
import enum


class VesselMailboxes(db.Model):
    __tablename__ = "vessel_mailboxes"

    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String, nullable=False)
    mailbox_id = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))


class VesselSequences(db.Model):
    __tablename__ = "vessel_sequences"

    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String, nullable=False)
    sequence_id = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))


class VesselAPICachedResponses(db.Model):
    __tablename__ = "vessel_api_cached_responses"

    id = db.Column(db.Integer, primary_key=True)
    vessel_access_token = db.Column(db.String, nullable=False)
    contact_id = db.Column(db.String, nullable=True)
    sequence_id = db.Column(db.String, nullable=True)

    response_json = db.Column(db.JSON, nullable=True)
