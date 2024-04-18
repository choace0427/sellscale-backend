from app import db


class Segment(db.Model):
    __tablename__ = "segment"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    segment_title = db.Column(db.String(255), nullable=False)
    filters = db.Column(db.JSON, nullable=False)

    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))

    parent_segment_id = db.Column(
        db.Integer, db.ForeignKey("segment.id"), nullable=True
    )

    def __repr__(self):
        return f"<Segment {self.id}>"

    def to_dict(self):
        from model_import import ClientSDR, ClientArchetype

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client_archetype: ClientArchetype = ClientArchetype.query.get(self.client_archetype_id)

        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "segment_title": self.segment_title,
            "filters": self.filters,
            "parent_segment_id": self.parent_segment_id,
            "client_sdr": client_sdr.to_dict(include_email_bank=False) if client_sdr else None,
            "client_archetype": client_archetype.to_dict() if client_archetype else None,
        }
