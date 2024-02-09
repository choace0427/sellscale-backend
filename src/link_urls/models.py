from app import db
import sqlalchemy as sa, enum


class LinkURL(db.Model):
    __tablename__ = "link_url"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)
    url = db.Column(db.String, nullable=False)
    tiny_url = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "url": self.url,
            "tiny_url": self.tiny_url,
        }
