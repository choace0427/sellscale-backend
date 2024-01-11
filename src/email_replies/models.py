from app import db

import enum
import sqlalchemy as sa

from src.prospecting.models import ProspectOverallStatus
from src.research.models import ResearchPointType


class EmailReplyFramework(db.Model):
    __tablename__ = "email_reply_framework"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(4000), nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )

    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)
    substatus = db.Column(db.String(255), nullable=True)

    template = db.Column(db.String, nullable=True)
    additional_instructions = db.Column(db.String, nullable=True)

    # Analytics
    times_used = db.Column(db.Integer, nullable=True, default=0)
    times_accepted = db.Column(db.Integer, nullable=True, default=0)

    # Research
    research_blocklist = db.Column(
        db.ARRAY(sa.Enum(ResearchPointType, create_constraint=False)),
        nullable=True,
    )  # This list is used to block research points during message generation
    use_account_research = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "active": self.active,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "overall_status": self.overall_status.value
            if self.overall_status
            else None,
            "substatus": self.substatus,
            "template": self.template,
            "additional_instructions": self.additional_instructions,
            "times_used": self.times_used,
            "times_accepted": self.times_accepted,
            "research_blocklist": [r.value for r in self.research_blocklist]
            if self.research_blocklist
            else [],
            "use_account_research": self.use_account_research,
        }
