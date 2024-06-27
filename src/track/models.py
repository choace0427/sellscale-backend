from app import db
import sqlalchemy as sa, enum


class TrackSource(db.Model):
    __tablename__ = "track_source"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    track_key = db.Column(db.String, nullable=False)

    verified = db.Column(db.Boolean, nullable=True, default=False)
    website_base = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"<TrackSource {self.id}>"

    def to_dict(self):
        return {"id": self.id, "client_id": self.client_id, "track_key": self.track_key}


class TrackEvent(db.Model):
    __tablename__ = "track_event"

    id = db.Column(db.Integer, primary_key=True)
    track_source_id = db.Column(db.Integer, db.ForeignKey("track_source.id"))
    event_type = db.Column(db.String, nullable=False)
    window_location = db.Column(db.String, nullable=False)
    ip_address = db.Column(db.String, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"))

    company_identify_api = db.Column(db.String, nullable=True)
    company_identify_payload = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<TrackEvent {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "track_source_id": self.track_source_id,
            "event_type": self.event_type,
            "window_location": self.window_location,
            "ip_address": self.ip_address,
            "company_id": self.company_id,
        }

class DeanonymizedContact(db.Model):
    __tablename__ = "deanonymized_contact"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    company = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    visited_date = db.Column(db.DateTime, nullable=False)
    linkedin = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=True)
    tag = db.Column(db.String, nullable=True)
    prospect_id = db.Column(db.String, nullable=True)
    location = db.Column(db.String, nullable=True)
    track_event_id = db.Column(db.Integer, db.ForeignKey("track_event.id"))

    def __repr__(self):
        return f"<DeanonymizedContact {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "company": self.company,
            "title": self.title,
            "visited_date": self.visited_date,
            "linkedin": self.linkedin,
            "email": self.email,
            "tag": self.tag,
            "prospect_id": self.prospect_id,
            "location": self.location,
            "track_event_id": self.track_event_id,
        }