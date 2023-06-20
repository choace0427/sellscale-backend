from app import db
import enum
from src.client.models import ClientArchetype

from src.prospecting.models import ProspectOverallStatus


class EmailLength(enum.Enum):
    SHORT = 'SHORT'
    MEDIUM = 'MEDIUM'
    LONG = 'LONG'


class BumpFrameworkEmail(db.Model):
    __tablename__ = "bump_framework_email"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    objective = db.Column(db.String(255), nullable=True)
    email_blocks = db.Column(db.ARRAY(db.String), nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True)

    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)
    substatus = db.Column(db.String(255), nullable=True)

    default = db.Column(db.Boolean, nullable=False, default=False)

    email_length = db.Column(db.Enum(EmailLength),
                            nullable=True, default=EmailLength.MEDIUM)
    bumped_count = db.Column(db.Integer, nullable=True, default=0)

    sellscale_default_generated = db.Column(
        db.Boolean, nullable=True, default=False)

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(
            self.client_archetype_id
        )

        return {
            "id": self.id,
            "title": self.title,
            "objective": self.description,
            "email_blocks": self.email_blocks,
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
