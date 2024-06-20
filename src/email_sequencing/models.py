import enum
from app import db
from sqlalchemy import CheckConstraint
import sqlalchemy as sa

from src.client.models import ClientArchetype

from src.prospecting.models import ProspectOverallStatus


class EmailSubjectLineTemplate(db.Model):
    __tablename__ = "email_subject_line_template"

    id = db.Column(db.Integer, primary_key=True)
    subject_line = db.Column(db.String(255), nullable=False)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )

    active = db.Column(db.Boolean, nullable=False, default=True)
    times_used = db.Column(db.Integer, nullable=False, default=0)
    times_accepted = db.Column(db.Integer, nullable=False, default=0)

    sellscale_generated = db.Column(db.Boolean, nullable=True, default=False)
    is_magic_subject_line = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(self.client_archetype_id)

        return {
            "id": self.id,
            "subject_line": self.subject_line,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_archetype": archetype.archetype if archetype else None,
            "active": self.active,
            "times_used": self.times_used,
            "times_accepted": self.times_accepted,
            "sellscale_generated": self.sellscale_generated,
            "is_magic_subject_line": self.is_magic_subject_line,
        }

class EmailSequenceStep(db.Model):
    __tablename__ = "email_sequence_step"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    email_blocks = db.Column(
        db.ARRAY(db.String), nullable=True
    )  # Deprecated. TODO: Remove

    active = db.Column(db.Boolean, nullable=False, default=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )

    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)
    substatus = db.Column(db.String(255), nullable=True)

    default = db.Column(db.Boolean, nullable=False, default=False)

    bumped_count = db.Column(db.Integer, nullable=True, default=0)

    sellscale_default_generated = db.Column(db.Boolean, nullable=True, default=False)

    template = db.Column(db.String, nullable=True)

    # Analytics
    times_used = db.Column(db.Integer, nullable=True, default=0)
    times_accepted = db.Column(db.Integer, nullable=True, default=0)
    times_replied = db.Column(db.Integer, nullable=True, default=0)

    sequence_delay_days = db.Column(db.Integer, nullable=True, default=0)

    transformer_blocklist = db.Column(
        db.ARRAY(db.String),
        nullable=True,
    )  # use this list to blocklist transformer durings message generation

    # Define a CheckConstraint to enforce the minimum value
    __table_args__ = (
        CheckConstraint(
            "sequence_delay_days >= 0", name="check_sequence_delay_days_positive"
        ),
    )

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(self.client_archetype_id)

        return {
            "id": self.id,
            "title": self.title,
            "email_blocks": self.email_blocks,
            "active": self.active,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_archetype": archetype.archetype if archetype else None,
            "overall_status": (
                self.overall_status.value if self.overall_status else None
            ),
            "substatus": self.substatus,
            "default": self.default,
            "bumped_count": self.bumped_count,
            "sellscale_default_generated": self.sellscale_default_generated,
            "template": self.template,
            "times_used": self.times_used,
            "times_accepted": self.times_accepted,
            "times_replied": self.times_replied,
            "sequence_delay_days": self.sequence_delay_days,
            "transformer_blocklist": (
                [t for t in self.transformer_blocklist]
                if self.transformer_blocklist
                else []
            ),
        }


class EmailSequenceStepToAssetMapping(db.Model):
    __tablename__ = "email_sequence_step_to_asset_mapping"

    id = db.Column(db.Integer, primary_key=True)
    email_sequence_step_id = db.Column(
        db.Integer, db.ForeignKey("email_sequence_step.id"), nullable=False
    )
    client_assets_id = db.Column(
        db.Integer, db.ForeignKey("client_assets.id"), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "email_sequence_step_id": self.email_sequence_step_id,
            "client_assets_id": self.client_assets_id,
        }


class EmailTemplateType(enum.Enum):
    SUBJECT_LINE = "SUBJECT_LINE"
    BODY = "BODY"


class EmailTemplatePool(db.Model):
    __tablename__ = "email_template_pool"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(4000), nullable=True)

    template = db.Column(db.String, nullable=False)
    template_type = db.Column(db.Enum(EmailTemplateType), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)

    transformer_blocklist = db.Column(
        db.ARRAY(db.String),
        nullable=True,
        default=[],
    )  # use this list to blocklist transformer durings message generation

    labels = db.Column(db.ARRAY(db.String), nullable=True)
    tone = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "template_type": self.template_type.value,
            "active": self.active,
            "transformer_blocklist": (
                [t for t in self.transformer_blocklist]
                if self.transformer_blocklist
                else []
            ),
            "labels": self.labels,
            "tone": self.tone,
        }


class EmailGraderEntry(db.Model):
    __tablename__ = "email_grader_entry"

    id = db.Column(db.Integer, primary_key=True)

    # Inputs
    input_subject_line = db.Column(db.String, nullable=False)
    input_body = db.Column(db.String, nullable=False)

    input_tracking_data = db.Column(db.JSON, nullable=True)

    # Outputs
    detected_company = db.Column(db.String, nullable=True)
    evaluated_score = db.Column(db.Integer, nullable=True)
    evaluated_feedback = db.Column(db.JSON, nullable=True)
    evaluated_tones = db.Column(db.JSON, nullable=True)
    evaluated_construction_subject_line = db.Column(db.String, nullable=True)
    evaluated_construction_spam_words_subject_line = db.Column(db.JSON, nullable=True)
    evaluated_construction_body = db.Column(db.String, nullable=True)
    evaluated_construction_spam_words_body = db.Column(db.JSON, nullable=True)
    evaluated_read_time_seconds = db.Column(db.Integer, nullable=True)
    evaluated_personalizations = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "input_subject_line": self.input_subject_line,
            "input_body": self.input_body,
            "detected_company": self.detected_company,
            "evaluated_score": self.evaluated_score,
            "evaluated_feedback": self.evaluated_feedback,
            "evaluated_tones": self.evaluated_tones,
            "evaluated_construction_subject_line": self.evaluated_construction_subject_line,
            "evaluated_construction_spam_words_subject_line": self.evaluated_construction_spam_words_subject_line,
            "evaluated_construction_body": self.evaluated_construction_body,
            "evaluated_construction_spam_words_body": self.evaluated_construction_spam_words_body,
            "evaluated_read_time_seconds": self.evaluated_read_time_seconds,
            "evaluated_personalizations": self.evaluated_personalizations,
        }
