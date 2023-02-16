from app import db
from sqlalchemy.dialects.postgresql import JSONB
import enum
import json


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


class ProspectStatus(enum.Enum):
    PROSPECTED = "PROSPECTED"

    NOT_QUALIFIED = "NOT_QUALIFIED"
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
            "SENT_OUTREACH": "Sent Outreach",
            "ACCEPTED": "Accepted",
            "RESPONDED": "Bumped",
            "ACTIVE_CONVO": "Active Convo",
            "SCHEDULING": "Scheduling",
            "NOT_INTERESTED": "Not Interested",
            "DEMO_SET": "Demo Set",
            "DEMO_WON": "Demo Won",
            "DEMO_LOSS": "Demo Loss",
        }

    def all_statuses():
        return [
            ProspectStatus.PROSPECTED,
            ProspectStatus.NOT_QUALIFIED,
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
    li_last_message_timestamp = db.Column(db.DateTime, nullable=True)
    li_is_last_message_from_sdr = db.Column(db.Boolean, nullable=True)
    li_last_message_from_prospect = db.Column(db.String, nullable=True)

    last_reviewed = db.Column(db.DateTime, nullable=True)
    times_bumped = db.Column(db.Integer, nullable=True)

    deactivate_ai_engagement = db.Column(db.Boolean, nullable=True)

    is_lead = db.Column(db.Boolean, nullable=True)

    def get_by_id(prospect_id: int):
        return Prospect.query.filter_by(id=prospect_id).first()

    def to_dict(self) -> dict:
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
            "approved_outreach_message_id": self.approved_outreach_message_id,
            "approved_prospect_email_id": self.approved_prospect_email_id,
            "client_sdr_id": self.client_sdr_id,
            "li_conversation_thread_id": self.li_conversation_thread_id,
            "li_last_message_timestamp": self.li_last_message_timestamp,
            "li_is_last_message_from_sdr": self.li_is_last_message_from_sdr,
            "li_last_message_from_prospect": self.li_last_message_from_prospect,
            "last_reviewed": self.last_reviewed,
            "times_bumped": self.times_bumped,
            "deactivate_ai_engagement": self.deactivate_ai_engagement,
            "is_lead": self.is_lead,
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


# map of to_status and from status
# ensure that the prospect's from_status is in the array of the value of
#   "to_status" index
VALID_FROM_STATUSES_MAP = {
    ProspectStatus.PROSPECTED: [],
    ProspectStatus.NOT_QUALIFIED: [
        ProspectStatus.PROSPECTED,
        ProspectStatus.SENT_OUTREACH,
        ProspectStatus.ACCEPTED,
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.SENT_OUTREACH: [
        ProspectStatus.PROSPECTED,
    ],
    ProspectStatus.ACCEPTED: [ProspectStatus.SENT_OUTREACH],
    ProspectStatus.RESPONDED: [ProspectStatus.ACCEPTED],
    ProspectStatus.ACTIVE_CONVO: [
        ProspectStatus.RESPONDED,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.SCHEDULING: [
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.NOT_INTERESTED: [
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
    ],
    ProspectStatus.DEMO_SET: [
        ProspectStatus.RESPONDED,
        ProspectStatus.ACTIVE_CONVO,
        ProspectStatus.SCHEDULING,
        ProspectStatus.NOT_INTERESTED,
    ],
    ProspectStatus.DEMO_WON: [ProspectStatus.DEMO_SET],
    ProspectStatus.DEMO_LOSS: [ProspectStatus.DEMO_SET],
}
