from app import db
from sqlalchemy.dialects.postgresql import JSONB
import enum
import json
from typing import Optional


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
            "REMOVED": 0,
            "PROSPECTED": 1,
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

    batch = db.Column(db.String, nullable=True)
    status = db.Column(db.Enum(ProspectStatus), nullable=True)
    overall_status = db.Column(db.Enum(ProspectOverallStatus), nullable=True)

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

    img_url = db.Column(db.String, nullable=True)
    img_expire = db.Column(db.Numeric(20, 0), server_default='0', nullable=False)

    __table_args__ = (
        db.Index('idx_li_urn_id', 'li_urn_id'),
    )

    def get_by_id(prospect_id: int):
        return Prospect.query.filter_by(id=prospect_id).first()

    def to_dict(
        self,
        return_messages: Optional[bool] = False,
        return_message_type: Optional[str] = None,
    ) -> dict:
        from src.email_outbound.models import ProspectEmail
        from src.message_generation.models import GeneratedMessage

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

        return {
            "id": self.id,
            "client_id": self.client_id,
            "archetype_id": self.archetype_id,
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
            "batch": self.batch,
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
            "img_url": self.img_url,
            "img_expire": self.img_expire,
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
    ],
    ProspectStatus.ACTIVE_CONVO: [
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.SCHEDULING: [
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_INTERESTED,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.DEMO_SET: [
        ProspectStatus.DEMO_WON,
        ProspectStatus.DEMO_LOSS,
    ],
    ProspectStatus.NOT_INTERESTED: [
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
        ProspectStatus.DEMO_SET,
        ProspectStatus.NOT_QUALIFIED,
    ],
    ProspectStatus.NOT_QUALIFIED: [],
    ProspectStatus.SEND_OUTREACH_FAILED: [ProspectStatus.PROSPECTED],   # Permissable to retry
    ProspectStatus.DEMO_WON: [],
    ProspectStatus.DEMO_LOSS: [ProspectStatus.DEMO_WON],
}
