from app import db
import enum
from src.client.models import ClientArchetype

from src.prospecting.models import ProspectOverallStatus


class BumpLength(enum.Enum):
    SHORT = 'SHORT'
    MEDIUM = 'MEDIUM'
    LONG = 'LONG'

class BumpFramework(db.Model):
    __tablename__ = "bump_framework"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(4000), nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)

    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)
    substatus = db.Column(db.String(255), nullable=True)

    default = db.Column(db.Boolean, nullable=False, default=False)

    bump_length = db.Column(db.Enum(BumpLength), nullable=True, default=BumpLength.MEDIUM)

    def to_dict(self, include_archetypes: bool = False):
        archetypes_details = []
        if include_archetypes:
            archetypes_details = self.get_archetype_details()

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "overall_status": self.overall_status.value if self.overall_status else None,
            "substatus": self.substatus,
            "active": self.active,
            "default": self.default,
            "bump_length": self.bump_length.value if self.bump_length else None,
            "archetypes": archetypes_details
        }

    def get_archetype_details(self) -> list[dict]:
        junctions: list[JunctionBumpFrameworkClientArchetype] = JunctionBumpFrameworkClientArchetype.query.filter(
            JunctionBumpFrameworkClientArchetype.bump_framework_id == self.id
        ).all()
        junction_archetype_ids = [j.client_archetype_id for j in junctions]
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.id.in_(junction_archetype_ids)
        ).all()

        return [
            {"archetype_id": archetype.id, "archetype_name": archetype.archetype}
            for archetype in archetypes
        ]


class JunctionBumpFrameworkClientArchetype(db.Model):
    __tablename__ = "junction_bump_framework_client_archetype"

    id = db.Column(db.Integer, primary_key=True)
    bump_framework_id = db.Column(db.Integer, db.ForeignKey("bump_framework.id"), nullable=False)
    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"), nullable=False)
