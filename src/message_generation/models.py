from src.bump_framework.models import BumpLength
from app import db
import enum
import sqlalchemy as sa


class GeneratedMessageStatus(enum.Enum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    APPROVED = "APPROVED"
    QUEUED_FOR_OUTREACH = "QUEUED_FOR_OUTREACH"
    FAILED_TO_SEND = "FAILED_TO_SEND"
    SENT = "SENT"


class GeneratedMessageType(enum.Enum):
    LINKEDIN = "LINKEDIN"
    EMAIL = "EMAIL"

    def all_types():
        return [
            GeneratedMessageType.LINKEDIN,
            GeneratedMessageType.EMAIL,
        ]


class GeneratedMessageJobStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GeneratedMessageEmailType(enum.Enum):
    SUBJECT_LINE = "SUBJECT_LINE"
    BODY = "BODY"


class GeneratedMessage(db.Model):
    __tablename__ = "generated_message"

    id = db.Column(db.Integer, primary_key=True)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    outbound_campaign_id = db.Column(
        db.Integer, db.ForeignKey("outbound_campaign.id"), nullable=True
    )
    research_points = db.Column(db.ARRAY(db.Integer), nullable=True)
    prompt = db.Column(db.String, nullable=False)
    completion = db.Column(db.String, nullable=False)
    message_status = db.Column(db.Enum(GeneratedMessageStatus), nullable=False)
    message_type = db.Column(db.Enum(GeneratedMessageType), nullable=True)
    date_sent = db.Column(db.DateTime, nullable=True)
    batch_id = db.Column(db.String, nullable=True)

    verified_for_send = db.Column(db.Boolean, nullable=True)
    ai_approved = db.Column(db.Boolean, nullable=True)  # AI approved (or UW approved)
    human_edited = db.Column(db.Boolean, nullable=True)

    adversarial_ai_prediction = db.Column(db.Boolean, nullable=True)
    sensitive_content_flag = db.Column(db.Boolean, nullable=True)
    message_cta = db.Column(
        db.Integer, db.ForeignKey("generated_message_cta.id"), nullable=True
    )

    unknown_named_entities = db.Column(db.ARRAY(db.String), nullable=True)
    problems = db.Column(db.ARRAY(db.String), nullable=True)
    blocking_problems = db.Column(db.ARRAY(db.String), nullable=True)
    highlighted_words = db.Column(db.ARRAY(db.String), nullable=True)

    good_message = db.Column(db.Boolean, nullable=True)
    few_shot_prompt = db.Column(db.String, nullable=True)
    generated_message_instruction_id = db.Column(
        db.Integer, db.ForeignKey("generated_message_instruction.id"), nullable=True
    )

    adversary_identified_mistake = db.Column(db.String, nullable=True)
    adversary_identified_fix = db.Column(db.String, nullable=True)

    stack_ranked_message_generation_configuration_id = db.Column(
        db.Integer,
        db.ForeignKey("stack_ranked_message_generation_configuration.id"),
        nullable=True,
    )

    failed_outreach_error = db.Column(db.String, nullable=True)

    pb_csv_count = db.Column(db.Integer, nullable=True, default=0)

    autocorrect_run_count = db.Column(db.Integer, nullable=True, default=0)
    before_autocorrect_problems = db.Column(db.ARRAY(db.String), nullable=True)
    before_autocorrect_text = db.Column(db.String, nullable=True)
    after_autocorrect_text = db.Column(db.String, nullable=True)

    priority_rating = db.Column(db.Integer, nullable=True)

    # Email
    email_type = db.Column(db.Enum(GeneratedMessageEmailType), nullable=True)
    email_subject_line_template_id = db.Column(
        db.Integer, db.ForeignKey("email_subject_line_template.id"), nullable=True
    )
    email_sequence_step_template_id = db.Column(
        db.Integer, db.ForeignKey("email_sequence_step.id"), nullable=True
    )

    # LinkedIn
    li_init_template_id = db.Column(
        db.Integer, db.ForeignKey("linkedin_initial_message_template.id"), nullable=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "outbound_campaign_id": self.outbound_campaign_id,
            "research_points": self.research_points,
            "prompt": self.prompt,
            "completion": self.completion,
            "message_status": (
                self.message_status.value if self.message_status else None
            ),
            "message_type": self.message_type.value if self.message_type else None,
            "date_sent": self.date_sent,
            "batch_id": self.batch_id,
            "verified_for_send": self.verified_for_send,
            "ai_approved": self.ai_approved,
            "human_edited": self.human_edited,
            "adversarial_ai_prediction": self.adversarial_ai_prediction,
            "sensitive_content_flag": self.sensitive_content_flag,
            "message_cta": self.message_cta,
            "unknown_named_entities": self.unknown_named_entities,
            "problems": self.problems,
            "blocking_problems": self.blocking_problems,
            "highlighted_words": self.highlighted_words,
            "good_message": self.good_message,
            "few_shot_prompt": self.few_shot_prompt,
            "generated_message_instruction_id": self.generated_message_instruction_id,
            "adversary_identified_mistake": self.adversary_identified_mistake,
            "adversary_identified_fix": self.adversary_identified_fix,
            "stack_ranked_message_generation_configuration_id": self.stack_ranked_message_generation_configuration_id,
            "priority_rating": self.priority_rating,
            "email_type": self.email_type.value if self.email_type else None,
            "email_subject_line_template_id": self.email_subject_line_template_id,
            "email_sequence_step_template_id": self.email_sequence_step_template_id,
            "li_init_template_id": self.li_init_template_id,
        }


class GeneratedMessageQueue(db.Model):
    __tablename__ = "generated_message_queue"
    # A queue of generated messages that have been sent out and need to be processed when we find/scrape the associated msg

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )

    nylas_message_id = db.Column(db.String, unique=True, index=True, nullable=True)
    li_message_urn_id = db.Column(db.String, unique=True, index=True, nullable=True)
    bump_framework_id = db.Column(db.Integer, db.ForeignKey("bump_framework.id"))
    bump_framework_title = db.Column(db.String, nullable=True)
    bump_framework_description = db.Column(db.String, nullable=True)
    bump_framework_length = db.Column(db.String, nullable=True)
    account_research_points = db.Column(db.ARRAY(db.String), nullable=True)


class SendStatus(enum.Enum):
    IN_QUEUE = "IN_QUEUE"
    PROCESSING = "PROCESSING"
    SENT = "SENT"


class GeneratedMessageAutoBump(db.Model):
    __tablename__ = "generated_message_auto_bump"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    latest_li_message_id = db.Column(
        db.Integer,
        db.ForeignKey("linkedin_conversation_entry.id"),
        unique=True,
        index=True,
        nullable=True,
    )
    message = db.Column(db.String, nullable=False)

    bump_framework_id = db.Column(
        db.Integer, db.ForeignKey("bump_framework.id"), nullable=True
    )
    bump_framework_title = db.Column(db.String, nullable=True)
    bump_framework_description = db.Column(db.String, nullable=True)
    bump_framework_length = db.Column(db.Enum(BumpLength), nullable=True)

    account_research_points = db.Column(db.ARRAY(db.String), nullable=True)

    send_status = db.Column(db.Enum(SendStatus), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "client_sdr_id": self.client_sdr_id,
            "latest_li_message_id": self.latest_li_message_id,
            "message": self.message,
            "bump_framework": {
                "id": self.bump_framework_id,
                "title": self.bump_framework_title,
                "description": self.bump_framework_description,
                "length": (
                    self.bump_framework_length.value
                    if self.bump_framework_length
                    else None
                ),
            },
            "account_research_points": self.account_research_points,
        }


class GeneratedMessageInstruction(db.Model):
    __tablename__ = "generated_message_instruction"

    id = db.Column(db.Integer, primary_key=True)

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    text_value = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=True)


class GeneratedMessageCTA(db.Model):
    __tablename__ = "generated_message_cta"

    id = db.Column(db.Integer, primary_key=True)

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    text_value = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=True)

    cta_type = db.Column(db.String, nullable=True)

    expiration_date = db.Column(db.DateTime, nullable=True)  # in UTC
    auto_mark_as_scheduling_on_acceptance = db.Column(
        db.Boolean, nullable=True, default=False
    )

    def get_active_ctas_for_archetype(archetype_id):
        return GeneratedMessageCTA.query.filter_by(
            archetype_id=archetype_id, active=True
        ).all()

    def to_dict(self):
        from src.message_generation.services import is_cta_active

        return {
            "id": self.id,
            "archetype_id": self.archetype_id,
            "text_value": self.text_value,
            "active": is_cta_active(self.id),
            "expiration_date": self.expiration_date,
            "cta_type": self.cta_type,
            "auto_mark_as_scheduling_on_acceptance": self.auto_mark_as_scheduling_on_acceptance,
        }


class GeneratedMessageCTAToAssetMapping(db.Model):
    __tablename__ = "generated_message_cta_to_asset_mapping"

    id = db.Column(db.Integer, primary_key=True)
    generated_message_cta_id = db.Column(
        db.Integer, db.ForeignKey("generated_message_cta.id"), nullable=False
    )
    client_assets_id = db.Column(
        db.Integer, db.ForeignKey("client_assets.id"), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "generated_message_cta_id": self.generated_message_cta_id,
            "client_assets_id": self.client_assets_id,
        }


class GeneratedMessageFeedback(db.Model):
    __tablename__ = "generated_message_feedback"

    id = db.Column(db.Integer, primary_key=True)

    generated_message_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id"), nullable=False
    )
    feedback_value = db.Column(db.String, nullable=False)


class GeneratedMessageJob(db.Model):
    __tablename__ = "generated_message_job"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    batch_id = db.Column(db.String, nullable=True)

    status = db.Column(db.Enum(GeneratedMessageJobStatus), nullable=False)
    error_message = db.Column(db.String, nullable=True)


class GeneratedMessageJobQueue(db.Model):
    __tablename__ = "generated_message_job_queue"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    outbound_campaign_id = db.Column(db.Integer, db.ForeignKey("outbound_campaign.id"))

    generated_message_cta_id = db.Column(
        db.Integer, db.ForeignKey("generated_message_cta.id"), nullable=True
    )

    status = db.Column(db.Enum(GeneratedMessageJobStatus), nullable=False)
    error_message = db.Column(db.String, nullable=True)
    attempts = db.Column(db.Integer, nullable=True)

    generated_message_type = db.Column(db.Enum(GeneratedMessageType), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "outbound_campaign_id": self.outbound_campaign_id,
            "status": self.status.value,
            "error_message": self.error_message,
            "attempts": self.attempts,
        }


class GeneratedMessageEditRecord(db.Model):
    __tablename__ = "generated_message_edit_record"

    id = db.Column(db.Integer, primary_key=True)
    generated_message_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id"), nullable=False
    )
    original_text = db.Column(db.String, nullable=False)
    edited_text = db.Column(db.String, nullable=False)

    editor_id = db.Column(db.Integer, db.ForeignKey("editor.id"), nullable=True)


class ConfigurationType(enum.Enum):
    STRICT = "STRICT"  # all transformers must be present to use configuration
    DEFAULT = "DEFAULT"  # if no better configuration present, use this configuration. randomly samples from selected transformers.


class StackRankedMessageGenerationConfiguration(db.Model):
    __tablename__ = "stack_ranked_message_generation_configuration"

    id = db.Column(db.Integer, primary_key=True)
    configuration_type = db.Column(db.Enum(ConfigurationType), nullable=False)
    generated_message_type = db.Column(db.Enum(GeneratedMessageType), nullable=False)
    research_point_types = db.Column(
        db.ARRAY(db.String),
        nullable=True,
    )
    instruction = db.Column(db.String, nullable=False)
    computed_prompt = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=True, default=True)
    always_enable = db.Column(db.Boolean, nullable=True, default=False)

    name = db.Column(db.String, nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)
    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    priority = db.Column(
        db.Integer, nullable=True
    )  # lower = less priority; higher = more priority

    prompt_1 = db.Column(db.String, nullable=True)
    completion_1 = db.Column(db.String, nullable=True)

    prompt_2 = db.Column(db.String, nullable=True)
    completion_2 = db.Column(db.String, nullable=True)

    prompt_3 = db.Column(db.String, nullable=True)
    completion_3 = db.Column(db.String, nullable=True)

    prompt_4 = db.Column(db.String, nullable=True)
    completion_4 = db.Column(db.String, nullable=True)

    prompt_5 = db.Column(db.String, nullable=True)
    completion_5 = db.Column(db.String, nullable=True)

    prompt_6 = db.Column(db.String, nullable=True)
    completion_6 = db.Column(db.String, nullable=True)

    prompt_7 = db.Column(db.String, nullable=True)
    completion_7 = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
            "configuration_type": self.configuration_type.value,
            "generated_message_type": self.generated_message_type.value,
            "research_point_types": self.research_point_types,
            "instruction": self.instruction,
            "computed_prompt": self.computed_prompt,
            "name": self.name,
            "client_id": self.client_id,
            "archetype_id": self.archetype_id,
            "priority": self.priority,
            "active": self.active,
            "always_enable": self.always_enable,
            "prompt_1": self.prompt_1,
            "completion_1": self.completion_1,
            "prompt_2": self.prompt_2,
            "completion_2": self.completion_2,
            "prompt_3": self.prompt_3,
            "completion_3": self.completion_3,
            "prompt_4": self.prompt_4,
            "completion_4": self.completion_4,
            "prompt_5": self.prompt_5,
            "completion_5": self.completion_5,
            "prompt_6": self.prompt_6,
            "completion_6": self.completion_6,
            "prompt_7": self.prompt_7,
            "completion_7": self.completion_7,
        }
