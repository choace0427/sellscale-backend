from app import db
import sqlalchemy as sa


class PhantomBusterConfig(db.Model):
    __tablename__ = "phantom_buster_config"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    google_sheets_uuid = db.Column(db.String, nullable=True)

    phantom_name = db.Column(db.String)
    phantom_uuid = db.Column(db.String)
