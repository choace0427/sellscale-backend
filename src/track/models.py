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
        return {"id": self.id, "client_id": self.client_id, "track_key": self.track_key, "verified": self.verified, "website_base": self.website_base}


class TrackEvent(db.Model):
    __tablename__ = "track_event"

    id = db.Column(db.Integer, primary_key=True)
    track_source_id = db.Column(db.Integer, db.ForeignKey("track_source.id"))
    event_type = db.Column(db.String, nullable=False)
    window_location = db.Column(db.String, nullable=False)
    ip_address = db.Column(db.String, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"))
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=True)

    company_identify_api = db.Column(db.String, nullable=True)
    company_identify_payload = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<TrackEvent {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
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
    icp_route_id = db.Column(db.Integer, db.ForeignKey("icp_routing.id"))

    prospect_id = db.Column(db.String, nullable=True)
    location = db.Column(db.String, nullable=True)
    company_size = db.Column(db.String, nullable=True)
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
            "company_size": self.company_size,
            "icp_route_id": self.icp_route_id,
        }
    
class ICPRouting(db.Model):
    __tablename__ = "icp_routing"

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    
    id = db.Column(db.Integer, primary_key=True)
    
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)

    filter_company = db.Column(db.String, nullable=False)
    filter_title = db.Column(db.String, nullable=False)
    filter_location = db.Column(db.String, nullable=False)
    filter_company_size = db.Column(db.String, nullable=False)
    ai_mode = db.Column(db.Boolean, nullable=True, default=True)
    rules = db.Column(db.ARRAY(db.JSON), nullable=True)
    priority = db.Column(db.Integer, nullable=True, default=1)

    segment_id = db.Column(db.Integer, db.ForeignKey("segment.id"), nullable=True)
    send_slack = db.Column(db.Boolean, nullable=False, default=False)

    active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "ai_mode": self.ai_mode,
            "rules": self.rules,
            "filter_company": self.filter_company,
            "filter_title": self.filter_title,
            "filter_location": self.filter_location,
            "filter_company_size": self.filter_company_size,
            "segment_id": self.segment_id,
            "send_slack": self.send_slack,
            "active": self.active,
        }