from app import db
import enum
from src.client.models import ClientArchetype
from src.research.models import ResearchPointType
import sqlalchemy as sa

from src.prospecting.models import ProspectOverallStatus


class BumpLength(enum.Enum):
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


class BumpFramework(db.Model):
    __tablename__ = "bump_framework"

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

    human_feedback = db.Column(db.String, nullable=True)

    default = db.Column(db.Boolean, nullable=False, default=False)

    bump_length = db.Column(
        db.Enum(BumpLength), nullable=True, default=BumpLength.MEDIUM
    )
    bumped_count = db.Column(db.Integer, nullable=True, default=0)
    bump_delay_days = db.Column(db.Integer, nullable=True, default=2)

    sellscale_default_generated = db.Column(db.Boolean, nullable=True, default=False)
    use_account_research = db.Column(db.Boolean, nullable=True, default=True)

    etl_num_times_used = db.Column(db.Integer, nullable=True, default=0)
    etl_num_times_converted = db.Column(db.Integer, nullable=True, default=0)

    bump_framework_template_name = db.Column(db.String, nullable=True)
    bump_framework_human_readable_prompt = db.Column(db.String, nullable=True)
    additional_context = db.Column(db.String, nullable=True, default="")

    transformer_blocklist = db.Column(
        db.ARRAY(sa.Enum(ResearchPointType, create_constraint=False)),
        nullable=True,
    )  # use this list to blocklist transformer durings message generation

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(self.client_archetype_id)

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "active": self.active,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_archetype": archetype.archetype if archetype else None,
            "overall_status": self.overall_status.value
            if self.overall_status
            else None,
            "substatus": self.substatus,
            "default": self.default,
            "bump_length": self.bump_length.value if self.bump_length else None,
            "bumped_count": self.bumped_count,
            "bump_delay_days": self.bump_delay_days,
            "sellscale_default_generated": self.sellscale_default_generated,
            "use_account_research": self.use_account_research,
            "etl_num_times_used": self.etl_num_times_used,
            "etl_num_times_converted": self.etl_num_times_converted,
            "transformer_blocklist": [t.value for t in self.transformer_blocklist]
            if self.transformer_blocklist
            else [],
            "additional_context": self.additional_context,
            "bump_framework_template_name": self.bump_framework_template_name,
            "bump_framework_human_readable_prompt": self.bump_framework_human_readable_prompt,
            "human_feedback": self.human_feedback,
        }


class JunctionBumpFrameworkClientArchetype(db.Model):
    __tablename__ = "junction_bump_framework_client_archetype"

    id = db.Column(db.Integer, primary_key=True)
    bump_framework_id = db.Column(
        db.Integer, db.ForeignKey("bump_framework.id"), nullable=False
    )
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )


class BumpFrameworkTemplates(db.Model):
    __tablename__ = "bump_framework_templates"

    id = db.Column(db.Integer, primary_key=True)

    tag = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    raw_prompt = db.Column(db.String, nullable=False)
    human_readable_prompt = db.Column(db.String, nullable=False)
    length = db.Column(db.String, nullable=False)
    tag = db.Column(db.String, nullable=True)

    labels = db.Column(db.ARRAY(db.String), nullable=True)
    tone = db.Column(db.String, nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)

    bumped_counts = db.Column(db.ARRAY(db.Integer), nullable=True)
    overall_statuses = db.Column(
        db.ARRAY(sa.Enum(ProspectOverallStatus, create_constraint=False)), nullable=True
    )

    transformer_blocklist = db.Column(
        db.ARRAY(sa.Enum(ResearchPointType, create_constraint=False)),
        nullable=True,
    )  # use this list to blocklist transformer durings message generation

    def to_dict(self):
        return {
            "id": self.id,
            "tag": self.tag,
            "name": self.name,
            "raw_prompt": self.raw_prompt,
            "human_readable_prompt": self.human_readable_prompt,
            "length": self.length,
            "active": self.active,
            "bumped_counts": self.bumped_counts,
            "overall_statuses": [o.value for o in self.overall_statuses]
            if self.overall_statuses
            else None,
            "transformer_blocklist": [t.value for t in self.transformer_blocklist]
            if self.transformer_blocklist
            else [],
        }

    # 'role-have-to-do-with': {
    #     "name": "Does your role have to do with?",
    #     "raw_prompt": "Do a short follow-up acknowledging they're busy using their role description - and that we'd love to chat about any [relevant painpoints their role may face]\n\nWhich pain points would this persona have? (bullet points)\nAnswer: \n- _________________",
    #     "human_readable_prompt": "Connect with their role and ask them if their role has anything to do with what you want to connect with them on",
    #     "length": 'MEDIUM',
    # },
