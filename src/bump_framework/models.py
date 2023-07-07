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
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True)

    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)
    substatus = db.Column(db.String(255), nullable=True)

    default = db.Column(db.Boolean, nullable=False, default=False)

    bump_length = db.Column(db.Enum(BumpLength),
                            nullable=True, default=BumpLength.MEDIUM)
    bumped_count = db.Column(db.Integer, nullable=True, default=0)
    bump_delay_days = db.Column(db.Integer, nullable=True, default=2)

    sellscale_default_generated = db.Column(
        db.Boolean, nullable=True, default=False)

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(
            self.client_archetype_id
        )

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "active": self.active,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_archetype": archetype.archetype if archetype else None,
            "overall_status": self.overall_status.value if self.overall_status else None,
            "substatus": self.substatus,
            "default": self.default,
            "bump_length": self.bump_length.value if self.bump_length else None,
            "bumped_count": self.bumped_count,
            "sellscale_default_generated": self.sellscale_default_generated,
        }


class JunctionBumpFrameworkClientArchetype(db.Model):
    __tablename__ = "junction_bump_framework_client_archetype"

    id = db.Column(db.Integer, primary_key=True)
    bump_framework_id = db.Column(db.Integer, db.ForeignKey(
        "bump_framework.id"), nullable=False)
    client_archetype_id = db.Column(db.Integer, db.ForeignKey(
        "client_archetype.id"), nullable=False)
