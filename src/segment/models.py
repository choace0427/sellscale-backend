from app import db


class Segment(db.Model):
    __tablename__ = "segment"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    segment_title = db.Column(db.String(255), nullable=False)
    filters = db.Column(db.JSON, nullable=False)

    parent_segment_id = db.Column(
        db.Integer, db.ForeignKey("segment.id"), nullable=True
    )

    def __repr__(self):
        return f"<Segment {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "segment_title": self.segment_title,
            "filters": self.filters,
        }
