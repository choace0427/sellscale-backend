from app import db
import enum


class VesselMailboxes(db.Model):
    __tablename__ = "vessel_mailboxes"

    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String, nullable=False)
    mailbox_id = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)


class VesselSequences(db.Model):
    __tablename__ = "vessel_sequences"

    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String, nullable=False)
    sequence_id = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
