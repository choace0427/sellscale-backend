from app import db
import enum

from src.prospecting.models import ProspectOverallStatus


class BumpFramework(db.Model):
    __tablename__ = "bump_framework"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=False)

    active = db.Column(db.Boolean, nullable=False, default=True)

    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "active": self.active,
        }
