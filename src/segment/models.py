from app import db
from src.contacts.models import SavedApolloQuery


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

    saved_apollo_query_id = db.Column(
        db.Integer, db.ForeignKey("saved_apollo_query.id")
    )

    autoscrape_enabled = db.Column(db.Boolean, default=False)
    current_scrape_page = db.Column(db.Integer, default=0)

    attached_segment_tag_ids = db.Column(db.ARRAY(db.Integer), default=[])

    is_market_map = db.Column(db.Boolean, nullable=True, default=False)

    def __repr__(self):
        return f"<Segment {self.id}>"

    def to_dict(self):
        from model_import import ClientSDR, ClientArchetype

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client_archetype: ClientArchetype = ClientArchetype.query.get(self.client_archetype_id)
        apollo_query: SavedApolloQuery = SavedApolloQuery.query.get(self.saved_apollo_query_id)

        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "segment_title": self.segment_title,
            "filters": self.filters,
            "parent_segment_id": self.parent_segment_id,
            "client_sdr": client_sdr.to_dict(include_email_bank=False) if client_sdr else None,
            "client_archetype": client_archetype.to_dict() if client_archetype else None,
            "saved_apollo_query_id": self.saved_apollo_query_id,
            "apollo_query": apollo_query.to_dict() if apollo_query else None,
            "autoscrape_enabled": self.autoscrape_enabled,
            "current_scrape_page": self.current_scrape_page,
            "is_market_map": self.is_market_map,
        }
        
class SegmentTags(db.Model):
    __tablename__ = "segment_tags"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    color = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "name": self.name,
            "color": self.color,
        }
