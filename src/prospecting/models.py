from app import db
from sqlalchemy.dialects.postgresql import JSONB
import enum
from typing import Optional

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

    def get_rank(self):
        ranks = {
            "PROSPECTED": 0,
            "REMOVED": 1,
            "SENT_OUTREACH": 2,
            "ACCEPTED": 3,
            "BUMPED": 4,
            "ACTIVE_CONVO": 5,
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

    # Temp solution
    ACTIVE_CONVO_QUESTION = "ACTIVE_CONVO_QUESTION"
    ACTIVE_CONVO_QUAL_NEEDED = "ACTIVE_CONVO_QUAL_NEEDED"
    ACTIVE_CONVO_OBJECTION = "ACTIVE_CONVO_OBJECTION"
    ACTIVE_CONVO_SCHEDULING = "ACTIVE_CONVO_SCHEDULING"
    ACTIVE_CONVO_NEXT_STEPS = "ACTIVE_CONVO_NEXT_STEPS"

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
                "sellscale_enum_val": ProspectOverallStatus.REMOVED.value,
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

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True)
    company = db.Column(db.String, nullable=True)
    company_url = db.Column(db.String, nullable=True)
    employee_count = db.Column(db.String, nullable=True)

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
    hunter_email_score = db.Column(db.Float, nullable=True)

    email_additional = db.Column(db.ARRAY(db.JSON), nullable=True)  # Extra emails
    # {"email": string, "comment": string}[]

    batch = db.Column(db.String, nullable=True)
    status = db.Column(db.Enum(ProspectStatus), nullable=True)
    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)

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

    vessel_contact_id = db.Column(db.String, nullable=True)
    vessel_crm_id = db.Column(db.String, nullable=True)

    icp_fit_score = db.Column(db.Integer, nullable=True)
    icp_fit_reason = db.Column(db.String, nullable=True)
    icp_fit_prompt_data = db.Column(db.String, nullable=True)
    icp_fit_error = db.Column(db.String, nullable=True)
    # account_research_description = db.Column(db.String, nullable=True)

    img_url = db.Column(db.String, nullable=True)
    img_expire = db.Column(db.Numeric(20, 0), server_default="0", nullable=False)

    demo_date = db.Column(db.DateTime, nullable=True)

    uuid = db.Column(db.String, nullable=True, unique=True, index=True)

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

        # Check if shallow_data is requested
        if shallow_data:
            return {
                "id": self.id,
                "full_name": self.full_name,
                "company": self.company,
                "title": self.title,
                "icp_fit_score": self.icp_fit_score,
                "icp_fit_reason": self.icp_fit_reason,
                "li_public_id": self.linkedin_url.split("/in/")[1].split("/")[0] if self.linkedin_url else None,
                "img_url": self.img_url,
            }

        # Get prospect email status if it exists
        p_email: ProspectEmail = ProspectEmail.query.filter_by(
            prospect_id=self.id
        ).first()
        p_email_status = None
        if p_email and p_email.outreach_status:
            p_email_status = p_email.outreach_status.value

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

        return {
            "id": self.id,
            "client_id": self.client_id,
            "archetype_id": self.archetype_id,
            "archetype_name": archetype_name,
            "company": self.company,
            "company_url": self.company_url,
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
            "overall_status": self.overall_status.value
            if self.overall_status
            else None,
            "email_status": p_email_status,
            "approved_outreach_message_id": self.approved_outreach_message_id,
            "approved_prospect_email_id": self.approved_prospect_email_id,
            "client_sdr_id": self.client_sdr_id,
            "li_conversation_thread_id": self.li_conversation_thread_id,
            "li_last_message_timestamp": self.li_last_message_timestamp,
            "li_is_last_message_from_sdr": self.li_is_last_message_from_sdr,
            "li_last_message_from_prospect": self.li_last_message_from_prospect,
            "li_num_followers": self.li_num_followers,
            "li_urn_id": self.li_urn_id,
            "health_check_score": self.health_check_score,
            "li_intent_score": self.li_intent_score,
            "email_intent_score": self.email_intent_score,
            "last_reviewed": self.last_reviewed,
            "times_bumped": self.times_bumped,
            "deactivate_ai_engagement": self.deactivate_ai_engagement,
            "is_lead": self.is_lead,
            "vessel_contact_id": self.vessel_contact_id,
            "vessel_crm_id": self.vessel_crm_id,
            "generated_message_info": generated_message_info,
            "icp_fit_score": self.icp_fit_score,
            "icp_fit_reason": self.icp_fit_reason,
            "icp_fit_error": self.icp_fit_error,
            "img_url": self.img_url,
            "img_expire": self.img_expire,
            "hidden_until": self.hidden_until,
            "hidden_reason": self.hidden_reason.value
            if self.hidden_reason is not None
            else None,
            "demo_date": self.demo_date,
            "email_data": p_email.to_dict() if p_email else {},
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


class ProspectUploadBatch(db.Model):
    __tablename__ = "prospect_upload_batch"

    id = db.Column(db.Integer, primary_key=True)
    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    batch_id = db.Column(db.String, nullable=False)
    num_prospects = db.Column(db.Integer, nullable=False)


class ProspectStatusRecords(db.Model):
    __tablename__ = "prospect_status_records"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    from_status = db.Column(db.Enum(ProspectStatus), nullable=True)
    to_status = db.Column(db.Enum(ProspectStatus), nullable=True)


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
        ISCRAPER_FAILED: The upload has failed because iScraper failed. (Note this will populate the iscraper_error_message field)
    """

    DUPLICATE = "DUPLICATE"
    ISCRAPER_FAILED = "ISCRAPER_FAILED"


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

        csv_row_data: The row data from the CSV, stored as a JSONB (slower to write, faster to read).
        csv_row_data_hash: The hash of the csv_row_data. (used for matching)
        upload_attempts: The number of times this prospect upload has been attempted.
        status: The status of the prospect upload.
        error_type: The error type of the prospect upload.
        iscraper_error_message: The error message from iScraper (because iScraper API is trash).
    """

    __tablename__ = "prospect_uploads"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    prospect_uploads_raw_csv_id = db.Column(
        db.Integer, db.ForeignKey("prospect_uploads_raw_csv.id")
    )

    csv_row_data = db.Column(JSONB, nullable=False)
    csv_row_hash = db.Column(db.String, nullable=False)
    upload_attempts = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(ProspectUploadsStatus), nullable=False)
    error_type = db.Column(db.Enum(ProspectUploadsErrorType), nullable=True)
    iscraper_error_message = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_archetype_id": self.client_archetype_id,
            "client_sdr_id": self.client_sdr_id,
            "prospect_uploads_raw_csv_id": self.prospect_uploads_raw_csv_id,
            "csv_row_data": self.csv_row_data,
            "csv_row_hash": self.csv_row_hash,
            "upload_attempts": self.upload_attempts,
            "status": self.status.value,
            "error_type": self.error_type.value if self.error_type else None,
            "iscraper_error_message": self.iscraper_error_message,
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
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.DEMO_SET,
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
    ],
    ProspectStatus.NOT_INTERESTED: [
        ProspectStatus.ACTIVE_CONVO,
        # ProspectStatus.SCHEDULING,
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.NOT_QUALIFIED: [],
    ProspectStatus.SEND_OUTREACH_FAILED: [
        ProspectStatus.PROSPECTED,  # Permissable to retry
        ProspectStatus.SENT_OUTREACH,  # Permissable to be moved.
    ],
    ProspectStatus.DEMO_WON: [],
    ProspectStatus.DEMO_LOSS: [ProspectStatus.DEMO_WON],
}
