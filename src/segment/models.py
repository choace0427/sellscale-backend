from app import db


class Segment(db.Model):
    __tablename__ = "segment"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    segment_title = db.Column(db.String(255), nullable=False)
    filters = db.Column(db.JSON, nullable=False)
