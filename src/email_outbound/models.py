import enum

from sqlalchemy.dialects.postgresql import JSONB

from app import db

"""
Create new email schema:
- client
- template name
- fields 1 -> n

generate_email_for_client()
- get template
create new prospect email
"""


class EmailCustomizedFieldTypes(enum.Enum):
    EMAIL_FIRST_LINE = "EMAIL_FIRST_LINE"  # email outbound first line


class EmailSchema(db.Model):
    __tablename__ = "email_schema"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "client_archetype_id": self.client_archetype_id,
        }


class ProspectEmailStatus(enum.Enum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    APPROVED = "APPROVED"
    SENT = "SENT"


class ProspectEmailOutreachStatus(enum.Enum):
    """
    - UNKNOWN: used for null values in the future
    - NOT_SENT: email has not been sent
    - BOUNCED: email has bounced
    - QUEUED_FOR_OUTREACH: email has been queued for outreach
    - SENT_OUTREACH: email has been sent
    - EMAIL_OPENED: email has been opened
    - BUMPED: email has been bumped
    - ACCEPTED: email has been accepted (clicked on link)
    - ACTIVE_CONVO: email has been accepted and a conversation has been started
    - SCHEDULING: a is being scheduled following a conversation
    - DEMO_SET: a demo has been set
    - DEMO_WON: a demo has been won
    - DEMO_LOST: a demo has been lost
    """

    UNKNOWN = "UNKNOWN"
    NOT_SENT = "NOT_SENT"
    BOUNCED = "BOUNCED"
    QUEUED_FOR_OUTREACH = "QUEUED_FOR_OUTREACH"
    SENT_OUTREACH = "SENT_OUTREACH"

    EMAIL_OPENED = "EMAIL_OPENED"
    ACCEPTED = "ACCEPTED"
    SCHEDULING = "SCHEDULING"
    BUMPED = "BUMPED"

    NOT_QUALIFIED = "NOT_QUALIFIED"
    ACTIVE_CONVO = "ACTIVE_CONVO"

    # Temp solution
    ACTIVE_CONVO_QUESTION = "ACTIVE_CONVO_QUESTION"
    ACTIVE_CONVO_QUAL_NEEDED = "ACTIVE_CONVO_QUAL_NEEDED"
    ACTIVE_CONVO_OBJECTION = "ACTIVE_CONVO_OBJECTION"
    ACTIVE_CONVO_SCHEDULING = "ACTIVE_CONVO_SCHEDULING"
    ACTIVE_CONVO_NEXT_STEPS = "ACTIVE_CONVO_NEXT_STEPS"
    ACTIVE_CONVO_REVIVAL = "ACTIVE_CONVO_REVIVAL"
    ACTIVE_CONVO_OOO = "ACTIVE_CONVO_OOO"
    ACTIVE_CONVO_REFERRAL = "ACTIVE_CONVO_REFERRAL"

    NOT_INTERESTED = "NOT_INTERESTED"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    DEMO_SET = "DEMO_SET"

    DEMO_WON = "DEMO_WON"
    DEMO_LOST = "DEMO_LOST"

    def to_dict():
        return {
            "NOT_SENT": "Not Sent",
            "BOUNCED": "Bounced",
            "SENT_OUTREACH": "Sent email",
            "EMAIL_OPENED": "Opened Email",
            "BUMPED": "Bumped",
            "ACCEPTED": "Accepted",
            "ACTIVE_CONVO": "Active Convo",
            "NOT_QUALIFIED": "Not Qualified",
            "ACTIVE_CONVO_QUESTION": "Active Convo - Question",
            "ACTIVE_CONVO_QUAL_NEEDED": "Active Convo - Qualification Needed",
            "ACTIVE_CONVO_OBJECTION": "Active Convo - Objection",
            "ACTIVE_CONVO_SCHEDULING": "Active Convo - Scheduling",
            "ACTIVE_CONVO_NEXT_STEPS": "Active Convo - Next Steps",
            "ACTIVE_CONVO_REVIVAL": "Active Convo - Revival",
            "ACTIVE_CONVO_OOO": "Active Convo - Out of Office",
            "ACTIVE_CONVO_REFERRAL": "Active Convo - Referral",
            "SCHEDULING": "Scheduling",
            "NOT_INTERESTED": "Not Interested",
            "UNSUBSCRIBED": "Unsubscribed",
            "DEMO_SET": "Demo Scheduled",
            "DEMO_WON": "Demo Complete",
            "DEMO_LOST": "Demo Missed",
        }

    def all_statuses():
        return [
            ProspectEmailOutreachStatus.UNKNOWN,
            ProspectEmailOutreachStatus.NOT_SENT,
            ProspectEmailOutreachStatus.BOUNCED,
            ProspectEmailOutreachStatus.SENT_OUTREACH,
            ProspectEmailOutreachStatus.EMAIL_OPENED,
            ProspectEmailOutreachStatus.ACCEPTED,
            ProspectEmailOutreachStatus.BUMPED,
            ProspectEmailOutreachStatus.NOT_QUALIFIED,
            ProspectEmailOutreachStatus.ACTIVE_CONVO,
            ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
            ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
            ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
            ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
            ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
            ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
            ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
            ProspectEmailOutreachStatus.SCHEDULING,
            ProspectEmailOutreachStatus.QUEUED_FOR_OUTREACH,
            ProspectEmailOutreachStatus.NOT_INTERESTED,
            ProspectEmailOutreachStatus.UNSUBSCRIBED,
            ProspectEmailOutreachStatus.DEMO_SET,
            ProspectEmailOutreachStatus.DEMO_WON,
            ProspectEmailOutreachStatus.DEMO_LOST,
        ]

    def status_descriptions() -> dict:
        """Returns a dictionary of status descriptions.

        Each status description includes:
        - name: the human-readable name of the status
        - description: a description of the status
        - enum_val: the enum value of the status used in the backend
        - sellscale_enum_val: the equivalent sellscale (overall) enum value
        """
        from src.prospecting.models import ProspectOverallStatus

        return {
            ProspectEmailOutreachStatus.UNKNOWN.value: {
                "name": "Unknown",
                "description": "Status of this Prospect is unknown, most likely awaiting further action.",
                "enum_val": ProspectEmailOutreachStatus.UNKNOWN.value,
                "sellscale_enum_val": ProspectOverallStatus.PROSPECTED.value,
            },
            ProspectEmailOutreachStatus.NOT_SENT.value: {
                "name": "Not Sent",
                "description": "Email has not been yet sent to this Prospect.",
                "enum_val": ProspectEmailOutreachStatus.NOT_SENT.value,
                "sellscale_enum_val": ProspectOverallStatus.PROSPECTED.value,
            },
            ProspectEmailOutreachStatus.BOUNCED.value: {
                "name": "Bounced",
                "description": "Email has bounced.",
                "enum_val": ProspectEmailOutreachStatus.BOUNCED.value,
                "sellscale_enum_val": ProspectOverallStatus.REMOVED.value,
            },
            ProspectEmailOutreachStatus.SENT_OUTREACH.value: {
                "name": "Sent Email",
                "description": "Email has been sent to this Prospect.",
                "enum_val": ProspectEmailOutreachStatus.SENT_OUTREACH.value,
                "sellscale_enum_val": ProspectOverallStatus.SENT_OUTREACH.value,
            },
            ProspectEmailOutreachStatus.EMAIL_OPENED.value: {
                "name": "Opened Email",
                "description": "Email has been opened by this Prospect.",
                "enum_val": ProspectEmailOutreachStatus.EMAIL_OPENED.value,
                "sellscale_enum_val": ProspectOverallStatus.BUMPED.value,
            },
            ProspectEmailOutreachStatus.ACCEPTED.value: {
                "name": "Accepted",
                "description": "Prospect clicked on a link in the email.",
                "enum_val": ProspectEmailOutreachStatus.ACCEPTED.value,
                "sellscale_enum_val": ProspectOverallStatus.ACCEPTED.value,
            },
            ProspectEmailOutreachStatus.BUMPED.value: {
                "name": "Bumped",
                "description": "Prospect has been bumped.",
                "enum_val": ProspectEmailOutreachStatus.BUMPED.value,
                "sellscale_enum_val": ProspectOverallStatus.BUMPED.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO.value: {
                "name": "Active Convo",
                "description": "Prospect has been engaged in an active conversation through email.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.SCHEDULING.value: {
                "name": "Scheduling",
                "description": "The Prospect is scheduling a time to meet.",
                "enum_val": ProspectEmailOutreachStatus.SCHEDULING.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.NOT_INTERESTED.value: {
                "name": "Not Interested",
                "description": "The Prospect is not interested.",
                "enum_val": ProspectEmailOutreachStatus.NOT_INTERESTED.value,
                "sellscale_enum_val": ProspectOverallStatus.REMOVED.value,
            },
            ProspectEmailOutreachStatus.UNSUBSCRIBED.value: {
                "name": "Unsubscribed",
                "description": "The Prospect has unsubscribed.",
                "enum_val": ProspectEmailOutreachStatus.UNSUBSCRIBED.value,
                "sellscale_enum_val": ProspectOverallStatus.REMOVED.value,
            },
            ProspectEmailOutreachStatus.DEMO_SET.value: {
                "name": "Demo Set",
                "description": "The Prospect has set a time to meet.",
                "enum_val": ProspectEmailOutreachStatus.DEMO_SET.value,
                "sellscale_enum_val": ProspectOverallStatus.DEMO.value,
            },
            ProspectEmailOutreachStatus.DEMO_WON.value: {
                "name": "Demo Won",
                "description": "The Prospect is engaged and interested in continuing, following a meeting.",
                "enum_val": ProspectEmailOutreachStatus.DEMO_WON.value,
                "sellscale_enum_val": ProspectOverallStatus.DEMO.value,
            },
            ProspectEmailOutreachStatus.DEMO_LOST.value: {
                "name": "Demo Lost",
                "description": "The Prospect is not interested in continuing, following a meeting.",
                "enum_val": ProspectEmailOutreachStatus.DEMO_LOST.value,
                "sellscale_enum_val": ProspectOverallStatus.DEMO.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION.value: {
                "name": "Active Convo - Question",
                "description": "The Prospect has a question.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED.value: {
                "name": "Active Convo - Qualification Needed",
                "description": "The Prospect's qualifications need to be clarified.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION.value: {
                "name": "Active Convo - Objection",
                "description": "The Prospect has an objection.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING.value: {
                "name": "Active Convo - Scheduling",
                "description": "The Prospect is discussing scheduling.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS.value: {
                "name": "Active Convo - Next Steps",
                "description": "The Prospect gave short reply and needs follow up.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL.value: {
                "name": "Active Convo - Revival",
                "description": "The Prospect has been revived.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
            ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO.value: {
                "name": "Active Convo - Out of Office",
                "description": "The Prospect is out of office.",
                "enum_val": ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO.value,
                "sellscale_enum_val": ProspectOverallStatus.ACTIVE_CONVO.value,
            },
        }

    def valid_next_statuses(current_status) -> dict:
        """Returns a dictionary of valid next statuses, given a ProspectEmailOutreachStatus.

        Contains information found in status_descriptions().
        """
        next_status_descriptions = {}
        all_status_descriptions = ProspectEmailOutreachStatus.status_descriptions()
        for status in VALID_NEXT_EMAIL_STATUSES.get(current_status, []):
            next_status_descriptions[status.value] = all_status_descriptions.get(
                status.value, {}
            )

        return next_status_descriptions


class ProspectEmail(db.Model):
    __tablename__ = "prospect_email"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    outbound_campaign_id = db.Column(
        db.Integer, db.ForeignKey("outbound_campaign.id"), nullable=True
    )
    email_status = db.Column(db.Enum(ProspectEmailStatus), nullable=True)
    outreach_status = db.Column(db.Enum(ProspectEmailOutreachStatus), nullable=True)

    personalized_first_line = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")
    )
    personalized_subject_line = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")
    )
    personalized_body = db.Column(db.Integer, db.ForeignKey("generated_message.id"))

    date_scheduled_to_send = db.Column(db.DateTime, nullable=True)  # in UTC
    date_sent = db.Column(db.DateTime, nullable=True)
    batch_id = db.Column(db.String, nullable=True)

    nylas_thread_id = db.Column(db.String, nullable=True)
    times_bumped = db.Column(db.Integer, nullable=True, default=0)

    # In UTC, used to hide prospects from the UI until a certain date
    hidden_until = db.Column(db.DateTime, nullable=True)
    last_reply_time = db.Column(db.DateTime, nullable=True)
    last_message = db.Column(db.String, nullable=True)

    # Smartlead
    smartlead_sent_count = db.Column(db.Integer, nullable=True, default=0)

    def to_dict(self):
        from src.message_generation.models import GeneratedMessage

        if self.personalized_first_line:
            personalized_first_line = GeneratedMessage.query.get(
                self.personalized_first_line
            ).to_dict()
        else:
            personalized_first_line = None

        if self.personalized_subject_line:
            personalized_subject_line = GeneratedMessage.query.get(
                self.personalized_subject_line
            ).to_dict()
        else:
            personalized_subject_line = None

        if self.personalized_body:
            personalized_body = GeneratedMessage.query.get(
                self.personalized_body
            ).to_dict()
        else:
            personalized_body = None

        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "outbound_campaign_id": self.outbound_campaign_id,
            "email_status": self.email_status.value if self.email_status else None,
            "outreach_status": (
                self.outreach_status.value if self.outreach_status else None
            ),
            "personalized_first_line": personalized_first_line,
            "personalized_subject_line": personalized_subject_line,
            "personalized_body": personalized_body,
            "date_scheduled_to_send": self.date_scheduled_to_send,
            "date_sent": self.date_sent,
            "batch_id": self.batch_id,
            "nylas_thread_id": self.nylas_thread_id,
            "times_bumped": self.times_bumped,
            "hidden_until": self.hidden_until,
            "last_reply_time": self.last_reply_time,
            "last_message": self.last_message,
            "smartlead_sent_count": self.smartlead_sent_count,
        }


class ProspectEmailStatusRecords(db.Model):
    """Records the status changes of a prospect_email

    `id`: id of the record
    `prospect_email_id`: id of the prospect_email
    `from_status`: status before the change
    `to_status`: status after the change
    `sales_engagement_interaction_ss_id`: id of the sales engagement interaction that caused the change
    """

    __tablename__ = "prospect_email_status_records"

    id = db.Column(db.Integer, primary_key=True)
    prospect_email_id = db.Column(db.Integer, db.ForeignKey("prospect_email.id"))
    from_status = db.Column(db.Enum(ProspectEmailOutreachStatus), nullable=False)
    to_status = db.Column(db.Enum(ProspectEmailOutreachStatus), nullable=False)

    sales_engagement_interaction_ss_id = db.Column(
        db.Integer, db.ForeignKey("sales_engagement_interaction_ss.id"), nullable=True
    )

    automated = db.Column(db.Boolean, nullable=True)


class EmailInteractionState(enum.Enum):
    """
    - UNKNOWN: used for null values in the future
    - EMAIL_SENT: email has been sent
    - EMAIL_OPENED: email has been opened
    - EMAIL_CLICKED: email has been clicked
    - EMAIL_REPLIED: email has been replied to
    """

    UNKNOWN = "UNKNOWN"

    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_OPENED = "EMAIL_OPENED"
    EMAIL_CLICKED = "EMAIL_CLICKED"
    EMAIL_REPLIED = "EMAIL_REPLIED"


class EmailSequenceState(enum.Enum):
    """
    - UNKNOWN: used for null values in the future
    - IN_PROGRESS: email sequence is in progress
    - COMPLETED: email sequence is completed
    - BOUNCED: email has bounced
    - OUT_OF_OFFICE: recipient replied with out of office message
    """

    UNKNOWN = "UNKNOWN"

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

    BOUNCED = "BOUNCED"
    OUT_OF_OFFICE = "OUT_OF_OFFICE"


class SalesEngagementInteractionSource(enum.Enum):
    """
    - OUTREACH: outreach interaction (from CSV)
    - SALESLOFT: salesloft interaction (from CSV)
    """

    OUTREACH = "OUTREACH"
    SALESLOFT = "SALESLOFT"


class SalesEngagementInteractionRaw(db.Model):
    __tablename__ = "sales_engagement_interaction_raw"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )

    csv_data = db.Column(JSONB, nullable=False)
    csv_data_hash = db.Column(db.String, nullable=False)
    source = db.Column(db.Enum(SalesEngagementInteractionSource), nullable=False)
    sequence_name = db.Column(db.String, nullable=False)


class SalesEngagementInteractionSS(db.Model):
    __tablename__ = "sales_engagement_interaction_ss"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    sales_engagement_interaction_raw_id = db.Column(
        db.Integer, db.ForeignKey("sales_engagement_interaction_raw.id"), nullable=False
    )

    ss_status_data = db.Column(JSONB, nullable=False)


# key (new_status) : value (list of valid statuses to update from)
VALID_UPDATE_EMAIL_STATUS_MAP = {
    ProspectEmailOutreachStatus.SENT_OUTREACH: [
        ProspectEmailOutreachStatus.UNKNOWN,
        ProspectEmailOutreachStatus.NOT_SENT,
    ],
    ProspectEmailOutreachStatus.UNSUBSCRIBED: [
        ProspectEmailOutreachStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.ACCEPTED,
    ],
    ProspectEmailOutreachStatus.BOUNCED: [
        ProspectEmailOutreachStatus.SENT_OUTREACH,
    ],
    ProspectEmailOutreachStatus.EMAIL_OPENED: [
        ProspectEmailOutreachStatus.SENT_OUTREACH,
    ],
    ProspectEmailOutreachStatus.ACCEPTED: [
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.SENT_OUTREACH,
    ],
    ProspectEmailOutreachStatus.BUMPED: [
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.ACCEPTED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO: [
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.BUMPED,
    ],
    ProspectEmailOutreachStatus.SCHEDULING: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.BUMPED,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.NOT_INTERESTED: [
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.BUMPED,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.DEMO_SET: [
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.BUMPED,
    ],
    ProspectEmailOutreachStatus.NOT_QUALIFIED: [
        ProspectEmailOutreachStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.BUMPED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
    ],
    ProspectEmailOutreachStatus.DEMO_WON: [ProspectEmailOutreachStatus.DEMO_SET],
    ProspectEmailOutreachStatus.DEMO_LOST: [ProspectEmailOutreachStatus.DEMO_SET],
}


EMAIL_ACTIVE_CONVO_POSITIVE_STATUSES = [
    ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
    ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
    ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
]


VALID_NEXT_EMAIL_STATUSES = {
    ProspectEmailOutreachStatus.UNKNOWN: [
        ProspectEmailOutreachStatus.NOT_SENT,
        ProspectEmailOutreachStatus.SENT_OUTREACH,
    ],
    ProspectEmailOutreachStatus.NOT_SENT: [
        ProspectEmailOutreachStatus.SENT_OUTREACH,
    ],
    ProspectEmailOutreachStatus.QUEUED_FOR_OUTREACH: [
        ProspectEmailOutreachStatus.SENT_OUTREACH,
    ],
    ProspectEmailOutreachStatus.SENT_OUTREACH: [
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
        ProspectEmailOutreachStatus.BOUNCED,
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,  # Sometimes we don't track email opens
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REFERRAL,
    ],
    ProspectEmailOutreachStatus.EMAIL_OPENED: [
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REFERRAL,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.BUMPED,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACCEPTED: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REFERRAL,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.BUMPED,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.BUMPED: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REFERRAL,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO: [
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REFERRAL,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.NOT_QUALIFIED: [
        ProspectEmailOutreachStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.BUMPED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_REFERRAL: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL: [
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO: [  # OOO is a special case where the Prospect had an automated response, so moving OOO anywhere is allowable to reset the status
        ProspectEmailOutreachStatus.SENT_OUTREACH,
        ProspectEmailOutreachStatus.EMAIL_OPENED,
        ProspectEmailOutreachStatus.ACCEPTED,
        ProspectEmailOutreachStatus.BUMPED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUESTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_QUAL_NEEDED,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_OBJECTION,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_SCHEDULING,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_NEXT_STEPS,
        ProspectEmailOutreachStatus.ACTIVE_CONVO_REVIVAL,
        ProspectEmailOutreachStatus.SCHEDULING,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.SCHEDULING: [
        ProspectEmailOutreachStatus.DEMO_SET,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
        ProspectEmailOutreachStatus.NOT_QUALIFIED,
    ],
    ProspectEmailOutreachStatus.DEMO_SET: [
        ProspectEmailOutreachStatus.DEMO_WON,
        ProspectEmailOutreachStatus.DEMO_LOST,
        ProspectEmailOutreachStatus.NOT_INTERESTED,
    ],
}


class SequenceStatus(enum.Enum):
    PENDING = "PENDING"
    IMPORTED = "IMPORTED"
    CANCELLED = "CANCELLED"


class Sequence(db.Model):
    __tablename__ = "sequence"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))
    data = db.Column(db.JSON, nullable=False)
    status = db.Column(db.Enum(SequenceStatus), nullable=False)
    sales_engagement_id = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "client_sdr_id": self.client_sdr_id,
            "archetype_id": self.archetype_id,
            "data": self.data,
            "status": self.status.value,
            "sales_engagement_id": self.sales_engagement_id,
        }


class EmailConversationThread(db.Model):
    __tablename__ = "email_conversation_thread"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    prospect_email = db.Column(db.String, nullable=False)
    sdr_email = db.Column(db.String, nullable=False)

    # Comes from Nylas --->
    subject = db.Column(db.String, nullable=True)
    snippet = db.Column(db.String, nullable=True)
    first_message_timestamp = db.Column(db.DateTime, nullable=True)
    last_message_received_timestamp = db.Column(db.DateTime, nullable=True)
    last_message_sent_timestamp = db.Column(db.DateTime, nullable=True)
    last_message_timestamp = db.Column(db.DateTime, nullable=True)
    participants = db.Column(db.ARRAY(db.JSON), nullable=True)
    has_attachments = db.Column(db.Boolean, nullable=True)
    unread = db.Column(db.Boolean, nullable=True)
    version = db.Column(db.Integer, nullable=True)
    nylas_thread_id = db.Column(db.String, nullable=False, index=True, unique=True)
    nylas_message_ids = db.Column(db.ARRAY(db.String), nullable=False)
    nylas_data_raw = db.Column(db.JSON, nullable=False)
    # <--- Comes from Nylas

    prospect_replied = db.Column(db.Boolean, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "prospect_id": self.prospect_id,
            "prospect_email": self.prospect_email,
            "sdr_email": self.sdr_email,
            "subject": self.subject,
            "snippet": self.snippet,
            "first_message_timestamp": self.first_message_timestamp,
            "last_message_received_timestamp": self.last_message_received_timestamp,
            "last_message_sent_timestamp": self.last_message_sent_timestamp,
            "last_message_timestamp": self.last_message_timestamp,
            "participants": self.participants,
            "has_attachments": self.has_attachments,
            "unread": self.unread,
            "version": self.version,
            "nylas_thread_id": self.nylas_thread_id,
            "nylas_message_ids": self.nylas_message_ids,
            "nylas_data_raw": self.nylas_data_raw,
            "prospect_replied": self.prospect_replied,
        }


class EmailConversationMessage(db.Model):
    __tablename__ = "email_conversation_message"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    prospect_email = db.Column(db.String, nullable=False)
    sdr_email = db.Column(db.String, nullable=False)
    from_sdr = db.Column(db.Boolean, nullable=True)
    from_prospect = db.Column(db.Boolean, nullable=True)

    ai_generated = db.Column(
        db.Boolean, nullable=True
    )  # is at least partially AI generated

    # Comes from Nylas --->
    subject = db.Column(db.String, nullable=True)
    snippet = db.Column(db.String, nullable=True)
    body = db.Column(db.String, nullable=True)
    bcc = db.Column(db.ARRAY(db.JSON), nullable=True)
    cc = db.Column(db.ARRAY(db.JSON), nullable=True)
    date_received = db.Column(db.DateTime, nullable=True)
    files = db.Column(db.ARRAY(db.JSON), nullable=True)
    message_from = db.Column(db.ARRAY(db.JSON), nullable=True)
    message_to = db.Column(db.ARRAY(db.JSON), nullable=True)
    reply_to = db.Column(db.ARRAY(db.JSON), nullable=True)
    email_conversation_thread_id = db.Column(
        db.Integer, db.ForeignKey("email_conversation_thread.id"), nullable=True
    )
    nylas_thread_id = db.Column(db.String, nullable=False)
    nylas_message_id = db.Column(db.String, nullable=False, index=True, unique=True)
    nylas_data_raw = db.Column(db.JSON, nullable=False)
    # <--- Comes from Nylas

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "prospect_id": self.prospect_id,
            "prospect_email": self.prospect_email,
            "sdr_email": self.sdr_email,
            "from_sdr": self.from_sdr,
            "from_prospect": self.from_prospect,
            "subject": self.subject,
            "snippet": self.snippet,
            "body": self.body,
            "bcc": self.bcc,
            "cc": self.cc,
            "date_received": self.date_received,
            "files": self.files,
            "message_from": self.message_from,
            "message_to": self.message_to,
            "reply_to": self.reply_to,
            "email_conversation_thread_id": self.email_conversation_thread_id,
            "nylas_thread_id": self.nylas_thread_id,
            "nylas_message_id": self.nylas_message_id,
            "nylas_data_raw": self.nylas_data_raw,
            "ai_generated": self.ai_generated,
        }
