import merge
from src.individual.models import Individual
from app import db
from sqlalchemy.dialects.postgresql import JSONB
import enum
from typing import Optional
from src.email_outbound.email_store.models import EmailStore
from src.utils.abstract.attr_utils import deep_get

from src.utils.hasher import generate_uuid


class ProspectHiddenReason(enum.Enum):
    RECENTLY_BUMPED = "RECENTLY_BUMPED"
    STATUS_CHANGE = "STATUS_CHANGE"
    MANUAL = "MANUAL"
    DEMO_SCHEDULED = "DEMO_SCHEDULED"


class ProspectChannels(enum.Enum):
    LINKEDIN = "LINKEDIN"
    EMAIL = "EMAIL"

    SELLSCALE = "SELLSCALE"

    def to_dict_verbose():
        """Returns a verbose dictionary of the channels, their available statuses, the statuses' descriptions, and a mapping of the status to the SellScale status."""
        from src.email_outbound.models import ProspectEmailOutreachStatus

        li_channel_verbose = {
            "name": "LinkedIn",
            "description": "LinkedIn outbound channel.",
            "statuses_available": [p.value for p in ProspectStatus.all_statuses()],
        }
        li_channel_verbose.update(ProspectStatus.status_descriptions())

        email_channel_verbose = {
            "name": "Email",
            "description": "Email outbound channel.",
            "statuses_available": [
                p.value for p in ProspectEmailOutreachStatus.all_statuses()
            ],
        }
        email_channel_verbose.update(ProspectEmailOutreachStatus.status_descriptions())

        sellscale_channel_verbose = {
            "name": "SellScale Overall Status",
            "description": "SellScale's overall status. A consolidation of all channels.",
            "statuses_available": [
                p.value for p in ProspectOverallStatus.all_statuses()
            ],
        }
        sellscale_channel_verbose.update(ProspectOverallStatus.status_descriptions())

        return {
            ProspectChannels.LINKEDIN.value: li_channel_verbose,
            ProspectChannels.EMAIL.value: email_channel_verbose,
            ProspectChannels.SELLSCALE.value: sellscale_channel_verbose,
        }

    def map_to_other_channel_enum(channel: str) -> enum.Enum:
        from src.email_outbound.models import ProspectEmailOutreachStatus

        if channel == ProspectChannels.LINKEDIN.value:
            return ProspectStatus
        elif channel == ProspectChannels.EMAIL.value:
            return ProspectEmailOutreachStatus
        elif channel == ProspectChannels.SELLSCALE.value:
            return ProspectOverallStatus
        else:
            raise Exception(f"Channel {channel} is not supported.")


class ProspectOverallStatus(enum.Enum):
    PROSPECTED = "PROSPECTED"
    SENT_OUTREACH = "SENT_OUTREACH"
    ACCEPTED = "ACCEPTED"
    BUMPED = "BUMPED"
    ACTIVE_CONVO = "ACTIVE_CONVO"
    DEMO = "DEMO"
    REMOVED = "REMOVED"
    NURTURE = "NURTURE"

    def get_rank(self):
        ranks = {
            "PROSPECTED": 0,
            "SENT_OUTREACH": 2,
            "ACCEPTED": 3,
            "BUMPED": 4,
            "NURTURE": 4.5,
            "ACTIVE_CONVO": 5,
            "REMOVED": 5.5,
            "DEMO": 6,
        }
        return ranks[self.value]

    def all_statuses():
        return [
            ProspectOverallStatus.PROSPECTED,
            ProspectOverallStatus.SENT_OUTREACH,
            ProspectOverallStatus.ACCEPTED,
            ProspectOverallStatus.BUMPED,
            ProspectOverallStatus.ACTIVE_CONVO,
            ProspectOverallStatus.DEMO,
            ProspectOverallStatus.REMOVED,
            ProspectOverallStatus.NURTURE,
        ]

    def status_descriptions() -> dict:
        return {
            ProspectOverallStatus.PROSPECTED.value: {
                "name": "Prospected",
                "description": "Prospect has been added to the system.",
                "enum_val": ProspectOverallStatus.PROSPECTED.value,
                "sellscale_enum_val": ProspectOverallStatus.PROSPECTED.value,
            },
            ProspectOverallStatus.SENT_OUTREACH.value: {
                "name": "Sent Outreach",
                "description": "Prospect has been sent some form of outreach.",
                "enum_val": ProspectOverallStatus.SENT_OUTREACH.value,
                "sellscale_enum_val": ProspectOverallStatus.SENT_OUTREACH.value,
            },
            ProspectOverallStatus.ACCEPTED.value: {
                "name": "Accepted",
                "description": "Prospect has accepted the outreach.",
                "enum_val": ProspectOverallStatus.ACCEPTED.value,
                "sellscale_enum_val": ProspectOverallStatus.ACCEPTED.value,
            },
            ProspectOverallStatus.BUMPED.value: {
                "name": "Bumped",
                "description": "The Prospect has been bumped by a follow-up message.",
                "enum_val": ProspectOverallStatus.BUMPED.value,
                "sellscale_enum_val": ProspectOverallStatus.BUMPED.value,
            },
            ProspectOverallStatus.ACTIVE_CONVO.value: {
                "name": "Active Convo",
                "description": "The Prospect has been engaged in an active conversation.",
                "enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectOverallStatus.DEMO.value: {
                "name": "Demo",
                "description": "The Prospect has been scheduled for a demo.",
                "enum_val": ProspectOverallStatus.DEMO.value,
                "sellscale_enum_val": ProspectOverallStatus.DEMO.value,
            },
            ProspectOverallStatus.REMOVED.value: {
                "name": "Removed",
                "description": "The Prospect has been removed from the system for some reason.",
                "enum_val": ProspectOverallStatus.REMOVED.value,
                "sellscale_enum_val": ProspectOverallStatus.REMOVED.value,
            },
            ProspectOverallStatus.NURTURE.value: {
                "name": "Nurture",
                "description": "The Prospect will be re-engaged with at a later date.",
                "enum_val": ProspectOverallStatus.NURTURE.value,
                "sellscale_enum_val": ProspectOverallStatus.NURTURE.value,
            },
        }


class ProspectStatus(enum.Enum):
    PROSPECTED = "PROSPECTED"

    NOT_QUALIFIED = "NOT_QUALIFIED"

    QUEUED_FOR_OUTREACH = "QUEUED_FOR_OUTREACH"
    SEND_OUTREACH_FAILED = "SEND_OUTREACH_FAILED"
    SENT_OUTREACH = "SENT_OUTREACH"

    ACCEPTED = "ACCEPTED"
    RESPONDED = "RESPONDED"  # responded / followed up / bumped
    ACTIVE_CONVO = "ACTIVE_CONVO"
    SCHEDULING = "SCHEDULING"

    NOT_INTERESTED = "NOT_INTERESTED"
    DEMO_SET = "DEMO_SET"

    DEMO_WON = "DEMO_WON"
    DEMO_LOSS = "DEMO_LOSS"

    ACTIVE_CONVO_QUESTION = "ACTIVE_CONVO_QUESTION"
    ACTIVE_CONVO_QUAL_NEEDED = "ACTIVE_CONVO_QUAL_NEEDED"
    ACTIVE_CONVO_OBJECTION = "ACTIVE_CONVO_OBJECTION"
    ACTIVE_CONVO_SCHEDULING = "ACTIVE_CONVO_SCHEDULING"
    ACTIVE_CONVO_NEXT_STEPS = "ACTIVE_CONVO_NEXT_STEPS"
    ACTIVE_CONVO_REVIVAL = "ACTIVE_CONVO_REVIVAL"
    ACTIVE_CONVO_CIRCLE_BACK = "ACTIVE_CONVO_CIRCLE_BACK"
    ACTIVE_CONVO_REFERRAL = "ACTIVE_CONVO_REFERRAL"
    ACTIVE_CONVO_QUEUED_FOR_SNOOZE = "ACTIVE_CONVO_QUEUED_FOR_SNOOZE"
    ACTIVE_CONVO_CONTINUE_SEQUENCE = "ACTIVE_CONVO_CONTINUE_SEQUENCE"
    ACTIVE_CONVO_BREAKUP = "ACTIVE_CONVO_BREAKUP"

    def to_dict():
        return {
            "PROSPECTED": "Prospected",
            "NOT_QUALIFIED": "Not Qualified",
            "QUEUED_FOR_OUTREACH": "Queued for Outreach",
            "SEND_OUTREACH_FAILED": "Send Outreach Failed",
            "SENT_OUTREACH": "Sent Outreach",
            "ACCEPTED": "Accepted",
            "RESPONDED": "Bumped",
            "ACTIVE_CONVO": "Active Convo",
            "SCHEDULING": "Scheduling",
            "NOT_INTERESTED": "Not Interested",
            "DEMO_SET": "Demo Set",
            "DEMO_WON": "Demo Complete",
            "DEMO_LOSS": "Demo Missed",
        }

    def all_statuses():
        return [
            ProspectStatus.PROSPECTED,
            ProspectStatus.NOT_QUALIFIED,
            ProspectStatus.QUEUED_FOR_OUTREACH,
            ProspectStatus.SEND_OUTREACH_FAILED,
            ProspectStatus.SENT_OUTREACH,
            ProspectStatus.ACCEPTED,
            ProspectStatus.RESPONDED,
            ProspectStatus.ACTIVE_CONVO,
            ProspectStatus.SCHEDULING,
            ProspectStatus.NOT_INTERESTED,
            ProspectStatus.DEMO_SET,
            ProspectStatus.DEMO_WON,
            ProspectStatus.DEMO_LOSS,
            ProspectStatus.ACTIVE_CONVO_QUESTION,
            ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
            ProspectStatus.ACTIVE_CONVO_OBJECTION,
            ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
            ProspectStatus.ACTIVE_CONVO_SCHEDULING,
            ProspectStatus.ACTIVE_CONVO_REVIVAL,
            ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
            ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
            ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ]

    def status_descriptions():
        """Returns a dictionary of status descriptions.

        Each status description includes:
        - name: the human-readable name of the status
        - description: a description of the status
        - enum_val: the enum value of the status used in the backend
        - sellscale_enum_val: the equivalent sellscale (overall) enum value
        """

        return {
            ProspectStatus.PROSPECTED.value: {
                "name": "Prospected",
                "description": "Prospect has been added to the system.",
                "enum_val": ProspectStatus.PROSPECTED.value,
                "sellscale_enum_val": ProspectOverallStatus.PROSPECTED.value,
            },
            ProspectStatus.NOT_QUALIFIED.value: {
                "name": "Not Qualified",
                "description": "Prospect is not qualified to receive outreach.",
                "enum_val": ProspectStatus.NOT_QUALIFIED.value,
                "sellscale_enum_val": ProspectOverallStatus.REMOVED.value,
            },
            ProspectStatus.QUEUED_FOR_OUTREACH.value: {
                "name": "Queued for Outreach",
                "description": "Prospect is queued for outreach.",
                "enum_val": ProspectStatus.QUEUED_FOR_OUTREACH.value,
                "sellscale_enum_val": ProspectOverallStatus.PROSPECTED.value,
            },
            ProspectStatus.SEND_OUTREACH_FAILED.value: {
                "name": "Send Outreach Failed",
                "description": "Outreach was unable to be sent to the Prospect.",
                "enum_val": ProspectStatus.SEND_OUTREACH_FAILED.value,
                "sellscale_enum_val": ProspectOverallStatus.REMOVED.value,
            },
            ProspectStatus.SENT_OUTREACH.value: {
                "name": "Sent Outreach",
                "description": "Prospect has been sent an invitation to connect on LinkedIn.",
                "enum_val": ProspectStatus.SENT_OUTREACH.value,
                "sellscale_enum_val": ProspectOverallStatus.SENT_OUTREACH.value,
            },
            ProspectStatus.ACCEPTED.value: {
                "name": "Accepted",
                "description": "Prospect has accepted the invitation to connect on LinkedIn.",
                "enum_val": ProspectStatus.ACCEPTED.value,
                "sellscale_enum_val": ProspectOverallStatus.ACCEPTED.value,
            },
            ProspectStatus.RESPONDED.value: {
                "name": "Bumped",
                "description": "The Prospect has been bumped by a follow-up message on LinkedIn",
                "enum_val": ProspectStatus.RESPONDED.value,
                "sellscale_enum_val": ProspectOverallStatus.BUMPED.value,
            },
            ProspectStatus.ACTIVE_CONVO.value: {
                "name": "Active Convo",
                "description": "The Prospect has been engaged in an active conversation on LinkedIn.",
                "enum_val": ProspectStatus.ACTIVE_CONVO.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.SCHEDULING.value: {
                "name": "Scheduling",
                "description": "The Prospect is scheduling a time to meet.",
                "enum_val": ProspectStatus.SCHEDULING.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.NOT_INTERESTED.value: {
                "name": "Not Interested",
                "description": "The Prospect is not interested.",
                "enum_val": ProspectStatus.NOT_INTERESTED.value,
                "sellscale_enum_val": ProspectOverallStatus.NURTURE.value,
            },
            ProspectStatus.DEMO_SET.value: {
                "name": "Demo Set",
                "description": "The Prospect has set a time to meet.",
                "enum_val": ProspectStatus.DEMO_SET.value,
                "sellscale_enum_val": ProspectOverallStatus.DEMO.value,
            },
            ProspectStatus.DEMO_WON.value: {
                "name": "Demo Complete",
                "description": "The Prospect is engaged and interested in continuing, following a meeting.",
                "enum_val": ProspectStatus.DEMO_WON.value,
                "sellscale_enum_val": ProspectOverallStatus.DEMO.value,
            },
            ProspectStatus.DEMO_LOSS.value: {
                "name": "Demo Missed",
                "description": "The Prospect is not interested in continuing, following a meeting.",
                "enum_val": ProspectStatus.DEMO_LOSS.value,
                "sellscale_enum_val": ProspectOverallStatus.DEMO.value,
            },
            ProspectStatus.ACTIVE_CONVO_QUESTION.value: {
                "name": "Active Convo - Question",
                "description": "The Prospect has a question.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_QUESTION.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED.value: {
                "name": "Active Convo - Qualification Needed",
                "description": "The Prospect's qualifications need to be clarified.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_OBJECTION.value: {
                "name": "Active Convo - Objection",
                "description": "The Prospect has an objection.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_OBJECTION.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_SCHEDULING.value: {
                "name": "Active Convo - Scheduling",
                "description": "The Prospect is discussing scheduling.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_SCHEDULING.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_NEXT_STEPS.value: {
                "name": "Active Convo - Next Steps",
                "description": "The Prospect gave short reply and needs follow up.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_NEXT_STEPS.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_REVIVAL.value: {
                "name": "Active Convo - Revival",
                "description": "The Prospect has been revived.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_REVIVAL.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE.value: {
                "name": "Active Convo - Queued for Snooze",
                "description": "The Prospect has been queued for snooze.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE.value: {
                "name": "Active Convo - Continue Sequence",
                "description": "The Prospect has been queued for a sequence continuation.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectStatus.ACTIVE_CONVO_BREAKUP.value: {
                "name": "Active Convo - Breakup",
                "description": "The Prospect is not interested or not qualified and will be recycled.",
                "enum_val": ProspectStatus.ACTIVE_CONVO_BREAKUP.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
        }

    def valid_next_statuses(current_status) -> dict:
        """Returns a dictionary of valid next statuses, given a ProspectStatus.

        Contains information found in status_descriptions().
        """
        next_status_descriptions = {}
        all_status_descriptions = ProspectStatus.status_descriptions()
        for status in VALID_NEXT_LINKEDIN_STATUSES.get(current_status, []):
            next_status_descriptions[status.value] = all_status_descriptions.get(
                status.value, {}
            )

        return next_status_descriptions


class Prospect(db.Model):
    __tablename__ = "prospect"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    segment_id = db.Column(db.Integer, db.ForeignKey("segment.id"), nullable=True)

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True)
    company = db.Column(db.String, nullable=True)
    company_size = db.Column(db.Integer, nullable=True)
    colloquialized_company = db.Column(db.String, nullable=True)
    colloquialized_title = db.Column(db.String, nullable=True)
    company_url = db.Column(db.String, nullable=True)
    employee_count = db.Column(db.String, nullable=True)

    original_company = db.Column(db.String, nullable=True)
    original_title = db.Column(db.String, nullable=True)

    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    full_name = db.Column(db.String, nullable=True)

    industry = db.Column(db.String, nullable=True)

    linkedin_url = db.Column(db.String, nullable=True)
    linkedin_bio = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    last_position = db.Column(db.String, nullable=True)

    twitter_url = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True)
    email_store_id = db.Column(db.ForeignKey("email_store.id"), nullable=True)
    email_score = db.Column(db.Float, nullable=True)
    valid_primary_email = db.Column(db.Boolean, nullable=True)

    email_additional = db.Column(db.ARRAY(db.JSON), nullable=True)  # Extra emails
    # {"email": string, "comment": string}[]

    batch = db.Column(db.String, nullable=True)
    status = db.Column(db.Enum(ProspectStatus), nullable=True)
    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)

    disqualification_reason = db.Column(db.String, nullable=True)

    hidden_until = db.Column(
        db.DateTime, nullable=True
    )  # in UTC, used to hide prospects from the UI until a certain date
    hidden_reason = db.Column(db.Enum(ProspectHiddenReason), nullable=True)

    approved_outreach_message_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")  # approved linkedin message
    )
    approved_prospect_email_id = db.Column(
        db.Integer, db.ForeignKey("prospect_email.id")  # approved prospect email id
    )

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    li_conversation_thread_id = db.Column(db.String, nullable=True)
    li_conversation_urn_id = db.Column(db.String, nullable=True)
    li_last_message_timestamp = db.Column(db.DateTime, nullable=True)
    li_is_last_message_from_sdr = db.Column(db.Boolean, nullable=True)
    li_last_message_from_prospect = db.Column(db.String, nullable=True)
    li_last_message_from_sdr = db.Column(db.String, nullable=True)
    li_unread_messages = db.Column(db.Integer, nullable=True)

    email_last_message_timestamp = db.Column(db.DateTime, nullable=True)
    email_is_last_message_from_sdr = db.Column(db.Boolean, nullable=True)
    email_last_message_from_prospect = db.Column(db.String, nullable=True)
    email_last_message_from_sdr = db.Column(db.String, nullable=True)
    email_unread_messages = db.Column(db.Integer, nullable=True)

    li_num_followers = db.Column(db.Integer, nullable=True)
    li_should_deep_scrape = db.Column(db.Boolean, nullable=True)
    li_urn_id = db.Column(db.String, nullable=True)

    health_check_score = db.Column(db.Float, nullable=True)
    li_intent_score = db.Column(db.Float, nullable=True)
    email_intent_score = db.Column(db.Float, nullable=True)

    last_reviewed = db.Column(db.DateTime, nullable=True)  # last message date
    times_bumped = db.Column(db.Integer, nullable=True)

    deactivate_ai_engagement = db.Column(db.Boolean, nullable=True)

    is_lead = db.Column(db.Boolean, nullable=True)

    icp_fit_score = db.Column(db.Integer, nullable=True)
    icp_fit_reason = db.Column(db.String, nullable=True)
    icp_fit_prompt_data = db.Column(db.String, nullable=True)
    icp_fit_error = db.Column(db.String, nullable=True)
    # account_research_description = db.Column(db.String, nullable=True)

    icp_fit_last_hash = db.Column(db.String, nullable=True)

    img_url = db.Column(db.String, nullable=True)
    img_expire = db.Column(db.Numeric(20, 0), server_default="0", nullable=False)

    demo_date = db.Column(db.DateTime, nullable=True)
    send_reminder = db.Column(db.Boolean, nullable=True)

    active = db.Column(db.Boolean, nullable=True)

    uuid = db.Column(db.String, nullable=True, unique=True, index=True)

    in_icp_sample = db.Column(db.Boolean, nullable=True)
    icp_fit_score_override = db.Column(db.Integer, nullable=True)

    individual_id = db.Column(db.Integer, db.ForeignKey("individual.id"), nullable=True)

    contract_size = db.Column(db.Integer, server_default="10000", nullable=False)

    is_lookalike_profile = db.Column(db.Boolean, nullable=True)

    education_1 = db.Column(db.String, nullable=True)
    education_2 = db.Column(db.String, nullable=True)

    prospect_location = db.Column(db.String, nullable=True)
    company_location = db.Column(db.String, nullable=True)

    meta_data = db.Column(db.JSON, nullable=True)

    merge_account_id = db.Column(db.String, nullable=True)
    merge_contact_id = db.Column(db.String, nullable=True)
    merge_opportunity_id = db.Column(db.String, nullable=True)
    merge_lead_id = db.Column(db.String, nullable=True)

    __table_args__ = (db.Index("idx_li_urn_id", "li_urn_id"),)

    def regenerate_uuid(self) -> str:
        uuid_str = generate_uuid(base=str(self.id), salt=self.full_name)
        self.uuid = uuid_str
        db.session.commit()

        return uuid_str

    def get_by_uuid(uuid: str):
        return Prospect.query.filter_by(uuid=uuid).first()

    def get_by_id(prospect_id: int):
        return Prospect.query.filter_by(id=prospect_id).first()

    def simple_to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company,
            "company_size": self.company_size,
            "title": self.title,
            "email": self.email,
            "valid_primary_email": self.valid_primary_email,
            "industry": self.industry,
            "icp_fit_score": self.icp_fit_score,
            "icp_fit_last_hash": self.icp_fit_last_hash,
            "icp_fit_reason": self.icp_fit_reason,
            "li_public_id": (
                self.linkedin_url.split("/in/")[1].split("/")[0]
                if self.linkedin_url
                else None
            ),
            "img_url": self.img_url,
            "archetype_id": self.archetype_id,
            "hidden_until": self.hidden_until,
            "hidden_reason": (
                self.hidden_reason.value if self.hidden_reason is not None else None
            ),
            "demo_date": self.demo_date,
            "deactivate_ai_engagement": self.deactivate_ai_engagement,
            "is_lead": self.is_lead,
            "overall_status": self.overall_status.value,
            "linkedin_status": self.status.value,
            "li_urn_id": self.li_urn_id,
            "li_conversation_urn_id": self.li_conversation_urn_id,
            "li_last_message_timestamp": self.li_last_message_timestamp,
            "li_is_last_message_from_sdr": self.li_is_last_message_from_sdr,
            "li_last_message_from_prospect": self.li_last_message_from_prospect,
            "li_last_message_from_sdr": self.li_last_message_from_sdr,
            "li_unread_messages": self.li_unread_messages,
            "email_last_message_timestamp": self.email_last_message_timestamp,
            "email_is_last_message_from_sdr": self.email_is_last_message_from_sdr,
            "email_last_message_from_prospect": self.email_last_message_from_prospect,
            "email_last_message_from_sdr": self.email_last_message_from_sdr,
            "email_unread_messages": self.email_unread_messages,
            "active": self.active,
            "in_icp_sample": self.in_icp_sample,
            "icp_fit_score_override": self.icp_fit_score_override,
            "contract_size": self.contract_size,
            "is_lookalike_profile": self.is_lookalike_profile,
            "original_company": self.original_company,
            "original_title": self.original_title,
            "colloquialized_company": self.colloquialized_company,
            "colloquialized_title": self.colloquialized_title,
            "education_1": self.education_1,
            "education_2": self.education_2,
            "prospect_location": self.prospect_location,
            "company_location": self.company_location,
            "meta_data": self.meta_data,
            "merge_account_id": self.merge_account_id,
            "merge_contact_id": self.merge_contact_id,
            "merge_opportunity_id": self.merge_opportunity_id,
            "merge_lead_id": self.merge_lead_id,
        }

    def to_dict(
        self,
        return_messages: Optional[bool] = False,
        return_message_type: Optional[str] = None,
        shallow_data: Optional[bool] = False,
        return_convo: Optional[bool] = False,
    ) -> dict:
        from src.email_outbound.models import (
            ProspectEmail,
            EmailConversationThread,
            EmailConversationMessage,
        )
        from src.message_generation.models import GeneratedMessage
        from src.client.models import ClientArchetype
        from src.li_conversation.models import LinkedinConversationEntry
        from src.research.models import ResearchPayload, ResearchType

        # Get prospect email status if it exists
        p_email: ProspectEmail = ProspectEmail.query.get(
            self.approved_prospect_email_id
        )
        p_email_status = None
        if p_email and p_email.outreach_status:
            p_email_status = p_email.outreach_status.value

        # Get prospect EmailStore information if it exists
        email_store_data = None
        if self.email_store_id:
            email_store: EmailStore = EmailStore.query.get(self.email_store_id)
            email_store_data = email_store.to_dict()

        # Get Prospect location information
        research_payload: ResearchPayload = ResearchPayload.query.filter_by(
            prospect_id=self.id, research_type=ResearchType.LINKEDIN_ISCRAPER.value
        ).first()
        location = None
        company_hq = None
        if research_payload and research_payload.payload:
            location = deep_get(research_payload.payload, "personal.location.default")
            company_hq = deep_get(
                research_payload.payload,
                "company.details.locations.headquarter.country",
            )

        # Check if shallow_data is requested
        if shallow_data:
            return {
                "id": self.id,
                "full_name": self.full_name,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "location": location,
                "company": self.company,
                "company_hq": company_hq,
                "company_size": self.company_size,
                "title": self.title,
                "email": self.email,
                "icp_fit_score": self.icp_fit_score,
                "icp_fit_last_hash": self.icp_fit_last_hash,
                "icp_fit_reason": self.icp_fit_reason,
                "li_public_id": (
                    self.linkedin_url.split("/in/")[1].split("/")[0]
                    if self.linkedin_url
                    else None
                ),
                "img_url": self.img_url,
                "archetype_id": self.archetype_id,
                "hidden_until": self.hidden_until,
                "hidden_reason": (
                    self.hidden_reason.value if self.hidden_reason is not None else None
                ),
                "demo_date": self.demo_date,
                "deactivate_ai_engagement": self.deactivate_ai_engagement,
                "is_lead": self.is_lead,
                "overall_status": self.overall_status.value,
                "linkedin_status": self.status.value,
                "email_status": p_email_status,
                "li_urn_id": self.li_urn_id,
                "li_conversation_urn_id": self.li_conversation_urn_id,
                "li_last_message_timestamp": self.li_last_message_timestamp,
                "li_is_last_message_from_sdr": self.li_is_last_message_from_sdr,
                "li_last_message_from_prospect": self.li_last_message_from_prospect,
                "li_last_message_from_sdr": self.li_last_message_from_sdr,
                "li_unread_messages": self.li_unread_messages,
                "valid_primary_email": self.valid_primary_email,
                "email_last_message_timestamp": self.email_last_message_timestamp,
                "email_is_last_message_from_sdr": self.email_is_last_message_from_sdr,
                "email_last_message_from_prospect": self.email_last_message_from_prospect,
                "email_last_message_from_sdr": self.email_last_message_from_sdr,
                "email_unread_messages": self.email_unread_messages,
                "active": self.active,
                "in_icp_sample": self.in_icp_sample,
                "icp_fit_score_override": self.icp_fit_score_override,
                "email_store": email_store_data,
                "contract_size": self.contract_size,
                "is_lookalike_profile": self.is_lookalike_profile,
                "meta_data": self.meta_data,
                "merge_account_id": self.merge_account_id,
                "merge_contact_id": self.merge_contact_id,
                "merge_opportunity_id": self.merge_opportunity_id,
                "merge_lead_id": self.merge_lead_id,
            }

        # Get generated message if it exists and is requested
        generated_message_info = {}
        if return_messages:
            if return_message_type == "LINKEDIN":
                generated_message: GeneratedMessage = GeneratedMessage.query.get(
                    self.approved_outreach_message_id
                )
            elif return_message_type == "EMAIL":
                generated_message: GeneratedMessage = GeneratedMessage.query.get(
                    self.approved_prospect_email_id
                )
            generated_message_info = (
                generated_message.to_dict() if generated_message else {}
            )

        # Get Archetype info
        archetype_name = None
        archetype: ClientArchetype = ClientArchetype.query.get(self.archetype_id)
        if archetype:
            archetype_name = archetype.archetype
        # Get last 5 messages of their most recent conversation
        recent_messages = {}
        if return_convo:
            if self.li_conversation_thread_id and (
                self.status.value.startswith("ACTIVE_CONVO")
                or self.status.value == "RESPONDED"
            ):
                recent_messages["li_convo"] = [
                    msg.to_dict()
                    for msg in LinkedinConversationEntry.query.filter(
                        LinkedinConversationEntry.conversation_url.ilike(
                            "%" + self.li_conversation_thread_id + "%"
                        )
                    )
                    .order_by(LinkedinConversationEntry.date.desc())
                    .limit(5)
                    .all()
                ]

            if p_email_status == "ACTIVE_CONVO" or p_email_status == "SCHEDULING":
                thread = (
                    EmailConversationThread.query.filter(
                        EmailConversationThread.client_sdr_id == self.client_sdr_id,
                        EmailConversationThread.prospect_id == self.id,
                    )
                    .order_by(EmailConversationThread.updated_at.desc())
                    .first()
                )

                if thread:
                    recent_messages["email_thread"] = thread.to_dict()
                    recent_messages["email_convo"] = [
                        msg.to_dict()
                        for msg in EmailConversationMessage.query.filter(
                            EmailConversationMessage.email_conversation_thread_id
                            == thread.id
                        )
                        .limit(5)
                        .all()
                    ]

        if self.individual_id:
            individual: Individual = Individual.query.get(self.individual_id)
            individual_data = individual.to_dict()
        else:
            individual_data = None

        return {
            "id": self.id,
            "client_id": self.client_id,
            "archetype_id": self.archetype_id,
            "archetype_name": archetype_name,
            "location": location,
            "company": self.company,
            "company_url": self.company_url,
            "company_size": self.company_size,
            "company_hq": company_hq,
            "employee_count": self.employee_count,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "industry": self.industry,
            "linkedin_url": self.linkedin_url,
            "linkedin_bio": self.linkedin_bio,
            "title": self.title,
            "last_position": self.last_position,
            "twitter_url": self.twitter_url,
            "email": self.email,
            "email_additional": self.email_additional,
            "batch": self.batch,
            "recent_messages": recent_messages,
            "status": self.status.value,
            "linkedin_status": self.status.value,
            "overall_status": (
                self.overall_status.value if self.overall_status else None
            ),
            "email_status": p_email_status,
            "approved_outreach_message_id": self.approved_outreach_message_id,
            "approved_prospect_email_id": self.approved_prospect_email_id,
            "client_sdr_id": self.client_sdr_id,
            "li_conversation_thread_id": self.li_conversation_thread_id,
            "li_conversation_urn_id": self.li_conversation_urn_id,
            "li_last_message_timestamp": self.li_last_message_timestamp,
            "li_is_last_message_from_sdr": self.li_is_last_message_from_sdr,
            "li_last_message_from_prospect": self.li_last_message_from_prospect,
            "li_last_message_from_sdr": self.li_last_message_from_sdr,
            "li_unread_messages": self.li_unread_messages,
            "li_num_followers": self.li_num_followers,
            "li_urn_id": self.li_urn_id,
            "health_check_score": self.health_check_score,
            "li_intent_score": self.li_intent_score,
            "email_intent_score": self.email_intent_score,
            "last_reviewed": self.last_reviewed,
            "times_bumped": self.times_bumped,
            "deactivate_ai_engagement": self.deactivate_ai_engagement,
            "is_lead": self.is_lead,
            "generated_message_info": generated_message_info,
            "icp_fit_score": self.icp_fit_score,
            "icp_fit_last_hash": self.icp_fit_last_hash,
            "icp_fit_reason": self.icp_fit_reason,
            "icp_fit_error": self.icp_fit_error,
            "img_url": self.img_url,
            "img_expire": self.img_expire,
            "hidden_until": self.hidden_until,
            "hidden_reason": (
                self.hidden_reason.value if self.hidden_reason is not None else None
            ),
            "demo_date": self.demo_date,
            "valid_primary_email": self.valid_primary_email,
            "email_data": p_email.to_dict() if p_email else {},
            "email_last_message_timestamp": self.email_last_message_timestamp,
            "email_is_last_message_from_sdr": self.email_is_last_message_from_sdr,
            "email_last_message_from_prospect": self.email_last_message_from_prospect,
            "email_last_message_from_sdr": self.email_last_message_from_sdr,
            "email_unread_messages": self.email_unread_messages,
            "in_icp_sample": self.in_icp_sample,
            "icp_fit_score_override": self.icp_fit_score_override,
            "email_store": email_store_data,
            "individual_data": individual_data,
            "contract_size": self.contract_size,
            "meta_data": self.meta_data,
            "merge_account_id": self.merge_account_id,
            "merge_contact_id": self.merge_contact_id,
            "merge_opportunity_id": self.merge_opportunity_id,
            "merge_lead_id": self.merge_lead_id,
        }


class ProspectEvent(db.Model):
    __tablename__ = "prospect_event"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    nylas_event_id = db.Column(db.String, nullable=False, unique=True, index=True)
    nylas_calendar_id = db.Column(db.String, nullable=False)

    title = db.Column(db.String, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String, nullable=False)

    meeting_info = db.Column(db.JSON, nullable=False)
    nylas_data_raw = db.Column(db.JSON, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "client_sdr_id": self.client_sdr_id,
            "nylas_event_id": self.nylas_event_id,
            "nylas_calendar_id": self.nylas_calendar_id,
            "title": self.title,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "meeting_info": self.meeting_info,
            "nylas_data_raw": self.nylas_data_raw,
        }


class ProspectStatusRecords(db.Model):
    __tablename__ = "prospect_status_records"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    from_status = db.Column(db.Enum(ProspectStatus), nullable=True)
    to_status = db.Column(db.Enum(ProspectStatus), nullable=True)
    automated = db.Column(db.Boolean, nullable=True)


class ProspectNote(db.Model):
    __tablename__ = "prospect_note"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    note = db.Column(db.String, nullable=False)

    def get_prospect_notes(prospect_id: int):
        return (
            ProspectNote.query.filter(ProspectNote.prospect_id == prospect_id)
            .order_by(ProspectNote.created_at.desc())
            .all()
        )

    def to_dict(self):
        return {
            "created_at": self.created_at,
            "id": self.id,
            "prospect_id": self.prospect_id,
            "note": self.note,
        }


class ProspectUploadsStatus(enum.Enum):
    """Enumeration of the statuses of a ProspectUpload.

    Attributes:
        UPLOAD_COMPLETE: The upload has completed successfully.
        UPLOAD_QUEUED: The upload is queued for processing.
        UPLOAD_FAILED: The upload has failed (external errors, such as iScraper API).
        UPLOAD_IN_PROGRESS: The upload is in progress (worker is attempting to create Prospect records).
        UPLOAD_NOT_STARTED: The upload has not started (this row has not been picked up by a worker).
        DISQUALIFIED: The upload has been disqualified (this row has been disqualified, example: duplicate).
    """

    UPLOAD_COMPLETE = "UPLOAD_COMPLETE"
    UPLOAD_QUEUED = "UPLOAD_QUEUED"
    UPLOAD_IN_PROGRESS = "UPLOAD_IN_PROGRESS"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    UPLOAD_NOT_STARTED = "UPLOAD_NOT_STARTED"

    DISQUALIFIED = "DISQUALIFIED"


class ProspectUploadsErrorType(enum.Enum):
    """Enumeration of the error type for a ProspectUpload.

    Attributes:
        DUPLICATE: The upload has been disqualified because it is a duplicate.
        ISCRAPER_FAILED: The upload has failed because iScraper failed. (Note this will populate the error_message field)
    """

    DUPLICATE = "DUPLICATE"
    ISCRAPER_FAILED = "ISCRAPER_FAILED"


class ProspectUploadSource(enum.Enum):
    """Enumeration of the source of a ProspectUpload."""

    CSV = "CSV"
    CONTACT_DATABASE = "CONTACT_DATABASE"
    LINKEDIN_LINK = "LINKEDIN_LINK"
    TRIGGERS = "TRIGGERS"
    UNKNOWN = "UNKNOWN"


class ProspectUploadHistory(db.Model):
    """Stores the high level data for and the type of an upload.

    Designed to be used with the ProspectUploads model and inspired by the design of ProspectUploadsRawCSV.
    """

    class ProspectUploadHistoryStatus(enum.Enum):
        """Enumeration of the statuses of a ProspectUploadHistory.

        Attributes:
            UPLOAD_COMPLETE: The upload has completed successfully.
            UPLOAD_QUEUED: The upload is queued for processing.
            UPLOAD_FAILED: The upload has failed completely. Rarely used.
            UPLOAD_IN_PROGRESS: The upload is in progress (worker is attempting to create Prospect records).
            UPLOAD_NOT_STARTED: The upload has not started (this row has not been picked up by a worker).
        """

        UPLOAD_COMPLETE = "UPLOAD_COMPLETE"
        UPLOAD_QUEUED = "UPLOAD_QUEUED"
        UPLOAD_IN_PROGRESS = "UPLOAD_IN_PROGRESS"
        UPLOAD_FAILED = "UPLOAD_FAILED"
        UPLOAD_NOT_STARTED = "UPLOAD_NOT_STARTED"

    __tablename__ = "prospect_upload_history"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    # Data related to the upload itself
    upload_name = db.Column(db.String, nullable=False)
    upload_size = db.Column(db.Integer, nullable=False)
    uploads_completed = db.Column(db.Integer, nullable=False)
    uploads_not_started = db.Column(db.Integer, nullable=False)
    uploads_in_progress = db.Column(db.Integer, nullable=False)
    uploads_failed = db.Column(db.Integer, nullable=False)
    uploads_other = db.Column(db.Integer, nullable=False)
    upload_source = db.Column(db.Enum(ProspectUploadSource), nullable=False)
    status = db.Column(db.Enum(ProspectUploadHistoryStatus), nullable=False)

    # Data related to the originator
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    client_segment_id = db.Column(
        db.Integer, db.ForeignKey("segment.id"), nullable=True
    )
    raw_data = db.Column(JSONB, nullable=False)
    raw_data_hash = db.Column(db.String, nullable=False)

    def to_dict(self, include_raw_data=False) -> dict:
        from src.client.models import ClientArchetype
        from src.segment.models import Segment

        # Get the most up-to-date analytics for this history
        self.update_status()

        archetype: ClientArchetype = ClientArchetype.query.get(self.client_archetype_id)
        segment: Segment = Segment.query.get(self.client_segment_id)
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_sdr_id": self.client_sdr_id,
            "upload_name": self.upload_name,
            "upload_size": self.upload_size,
            "uploads_completed": self.uploads_completed,
            "uploads_not_started": self.uploads_not_started,
            "uploads_in_progress": self.uploads_in_progress,
            "uploads_failed": self.uploads_failed,
            "uploads_other": self.uploads_other,
            "upload_source": self.upload_source.value,
            "status": self.status.value,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_name": archetype.archetype if archetype else None,
            "client_segment_id": self.client_segment_id,
            "client_segment_name": segment.segment_title if segment else None,
            "raw_data": self.raw_data if include_raw_data else None,
            "raw_data_hash": self.raw_data_hash,
            "created_at": str(self.created_at),
        }

    def update_status(self):
        """Updates own status and uploads_completed by querying ProspectUploads table."""
        if self.status == self.ProspectUploadHistoryStatus.UPLOAD_COMPLETE:
            return

        # Get the number of uploads created by this history
        uploads: list[ProspectUploads] = ProspectUploads.query.filter(
            ProspectUploads.prospect_upload_history_id == self.id
        ).all()
        if not uploads:
            return

        # COMPLETE
        complete = [
            upload
            for upload in uploads
            if upload.status == ProspectUploadsStatus.UPLOAD_COMPLETE
        ]

        # NOT STARTED
        not_started = [
            upload
            for upload in uploads
            if upload.status == ProspectUploadsStatus.UPLOAD_NOT_STARTED
            or upload.status == ProspectUploadsStatus.UPLOAD_QUEUED
        ]

        # FAILED
        failed = [
            upload
            for upload in uploads
            if upload.status == ProspectUploadsStatus.UPLOAD_FAILED
            or upload.status == ProspectUploadsStatus.DISQUALIFIED
        ]

        # IN PROGRESS
        in_progress = [
            upload
            for upload in uploads
            if upload.status == ProspectUploadsStatus.UPLOAD_IN_PROGRESS
        ]

        # # OTHER
        # other = [
        #     upload
        #     for upload in uploads
        #     if upload.status == ProspectUploadsStatus.DISQUALIFIED
        # ]

        self.uploads_completed = len(complete)
        self.uploads_not_started = len(not_started)
        self.uploads_failed = len(failed)
        self.uploads_in_progress = len(in_progress)

        if in_progress:
            self.status = self.ProspectUploadHistoryStatus.UPLOAD_IN_PROGRESS
        else:
            self.status = self.ProspectUploadHistoryStatus.UPLOAD_COMPLETE

        db.session.commit()
        return


class ProspectUploadsRawCSV(db.Model):
    """Stores the raw CSV data for a prospect upload.

    Useful if we need to reference the raw CSV for a prospect upload in order to debug.

    Should be referenced by the ProspectUploads model.
    """

    __tablename__ = "prospect_uploads_raw_csv"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    csv_data = db.Column(JSONB, nullable=False)
    csv_data_hash = db.Column(db.String, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_archetype_id": self.client_archetype_id,
            "client_sdr_id": self.client_sdr_id,
            "csv_data_hash": self.csv_data_hash,
            "created_at": str(self.created_at),
        }


class ProspectUploads(db.Model):
    """Each row is a prospect to be uploaded by a worker.

    Attributes:
        id: The id of the prospect upload.
        client_id: The id of the client. (used for matching)
        client_archetype_id: The id of the client archetype. (used for matching)
        client_sdr_id: The id of the client sdr. (used for matching)
        prospect_uploads_raw_csv_id: The id of the raw CSV data for this prospect upload.

        data: The row data from the CSV, stored as a JSONB (slower to write, faster to read).
        data_hash: The hash of the data. (used for matching)
        upload_attempts: The number of times this prospect upload has been attempted.
        status: The status of the prospect upload.
        error_type: The error type of the prospect upload.
        error_message: The error message from the prospect upload.
    """

    __tablename__ = "prospect_uploads"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    prospect_uploads_raw_csv_id = db.Column(
        db.Integer, db.ForeignKey("prospect_uploads_raw_csv.id")
    )

    prospect_upload_history_id = db.Column(
        db.Integer, db.ForeignKey("prospect_upload_history.id")
    )

    upload_source = db.Column(db.Enum(ProspectUploadSource), nullable=True)
    data = db.Column(JSONB, nullable=False)
    data_hash = db.Column(db.String, nullable=False)
    upload_attempts = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(ProspectUploadsStatus), nullable=False)
    error_type = db.Column(db.Enum(ProspectUploadsErrorType), nullable=True)
    error_message = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_archetype_id": self.client_archetype_id,
            "client_sdr_id": self.client_sdr_id,
            "prospect_uploads_raw_csv_id": self.prospect_uploads_raw_csv_id,
            "upload_source": self.upload_source.value,
            "data": self.data,
            "data_hash": self.data_hash,
            "upload_attempts": self.upload_attempts,
            "status": self.status.value,
            "error_type": self.error_type.value if self.error_type else None,
            "error_message": self.error_message,
        }


VALID_NEXT_LINKEDIN_STATUSES = {
    ProspectStatus.PROSPECTED: [
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.QUEUED_FOR_OUTREACH,
        ProspectStatus.SENT_OUTREACH,
    ],
    ProspectStatus.QUEUED_FOR_OUTREACH: [
        ProspectStatus.SEND_OUTREACH_FAILED,
        ProspectStatus.SENT_OUTREACH,
    ],
    ProspectStatus.SENT_OUTREACH: [
        ProspectStatus.ACCEPTED,
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.ACCEPTED: [
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.RESPONDED: [
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.RESPONDED,
    ],
    ProspectStatus.ACTIVE_CONVO: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_REVIVAL,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_OBJECTION: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_REVIVAL,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_REVIVAL,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_QUESTION: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_REVIVAL,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_SCHEDULING: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_REVIVAL,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_NEXT_STEPS: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_REVIVAL,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_REVIVAL: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE: [
        ProspectStatus.NOT_INTERESTED,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO_BREAKUP,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.DEMO_SET,
    ],
    ProspectStatus.ACTIVE_CONVO_BREAKUP: [
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_OBJECTION,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectStatus.ACTIVE_CONVO_QUESTION,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectStatus.ACTIVE_CONVO_REVIVAL,
        ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
        ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
        ProspectStatus.ACTIVE_CONVO,
    ],
    ProspectStatus.SCHEDULING: [
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.NOT_QUALIFIED,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
    ],
    ProspectStatus.DEMO_SET: [
        ProspectStatus.DEMO_WON,
        ProspectStatus.DEMO_LOSS,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING,
    ],
    ProspectStatus.NOT_INTERESTED: [
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.NOT_QUALIFIED: [],
    ProspectStatus.SEND_OUTREACH_FAILED: [
        ProspectStatus.PROSPECTED,  # Permissable to retry
        ProspectStatus.SENT_OUTREACH,  # Permissable to be moved.
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.DEMO_WON: [],
    ProspectStatus.DEMO_LOSS: [ProspectStatus.DEMO_WON],
}


class ProspectReferral(db.Model):
    __tablename__ = "prospect_referral"

    referral_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), primary_key=True)
    referred_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), primary_key=True)

    meta_data = db.Column(db.JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            "referral_id": self.referral_id,
            "referred_id": self.referred_id,
            "meta_data": self.meta_data,
        }


class ExistingContact(db.Model):
    __tablename__ = "existing_contact"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    full_name = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    individual_id = db.Column(db.Integer, db.ForeignKey("individual.id"), nullable=True)

    company_name = db.Column(db.String, nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True)

    connection_source = db.Column(db.String, nullable=True)
    notes = db.Column(db.String, nullable=True)

    used = db.Column(db.Boolean, default=False)

    def to_dict(self, include_individual=True) -> dict:
        if self.individual_id and include_individual:
            individual: Individual = Individual.query.get(self.individual_id)
            individual_data = individual.to_dict()
        else:
            individual_data = None

        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "full_name": self.full_name,
            "title": self.title,
            "individual_data": individual_data,
            "company_name": self.company_name,
            "company_id": self.company_id,
            "connection_source": self.connection_source,
            "notes": self.notes,
            "used": self.used,
        }


class ProspectMessageFeedback(db.Model):
    __tablename__ = "prospect_message_feedback"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    li_msg_id = db.Column(
        db.Integer, db.ForeignKey("linkedin_conversation_entry.id"), nullable=True
    )
    email_msg_id = db.Column(
        db.Integer, db.ForeignKey("email_conversation_message.id"), nullable=True
    )
    rating = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.String, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "prospect_id": self.prospect_id,
            "li_msg_id": self.li_msg_id,
            "email_msg_id": self.email_msg_id,
            "rating": self.rating,
            "feedback": self.feedback,
        }


class ProspectInSmartlead(db.Model):
    """Very simple table. Tells us: Is this prospect in Smartlead? If not, let's investigate why not."""

    __tablename__ = "prospect_in_smartlead"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))  # The prospect
    in_smartlead = db.Column(
        db.Boolean, nullable=True
    )  # If the prospect is in Smartlead
    log = db.Column(
        db.ARRAY(db.String), nullable=True
    )  # What stage of the process to get added to Smartlead are we in

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "in_smartlead": self.in_smartlead,
            "log": self.log,
        }
