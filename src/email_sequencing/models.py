from app import db
from src.client.models import ClientArchetype

from src.prospecting.models import ProspectOverallStatus


class EmailSubjectLineTemplate(db.Model):
    __tablename__ = "email_subject_line_template"

    id = db.Column(db.Integer, primary_key=True)
    subject_line = db.Column(db.String(255), nullable=False)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)
    times_used = db.Column(db.Integer, nullable=False, default=0)
    times_accepted = db.Column(db.Integer, nullable=False, default=0)

    sellscale_generated = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(
            self.client_archetype_id
        )

        return {
            "id": self.id,
            "subject_line": self.subject_line,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_archetype": archetype.archetype if archetype else None,
            "active": self.active,
            "times_used": self.times_used,
            "times_accepted": self.times_accepted,
            "sellscale_generated": self.sellscale_generated
        }


class EmailSequenceStep(db.Model):
    __tablename__ = "email_sequence_step"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    email_blocks = db.Column(db.ARRAY(db.String), nullable=True) # Deprecated. TODO: Remove

    active = db.Column(db.Boolean, nullable=False, default=True)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True)

    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)
    substatus = db.Column(db.String(255), nullable=True)

    default = db.Column(db.Boolean, nullable=False, default=False)

    bumped_count = db.Column(db.Integer, nullable=True, default=0)

    sellscale_default_generated = db.Column(
        db.Boolean, nullable=True, default=False)

    template = db.Column(db.String, nullable=True)

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(
            self.client_archetype_id
        )

        return {
            "id": self.id,
            "title": self.title,
            "email_blocks": self.email_blocks,
            "active": self.active,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_archetype": archetype.archetype if archetype else None,
            "overall_status": self.overall_status.value if self.overall_status else None,
            "substatus": self.substatus,
            "default": self.default,
            "bumped_count": self.bumped_count,
            "sellscale_default_generated": self.sellscale_default_generated,
            "template": self.template
        }