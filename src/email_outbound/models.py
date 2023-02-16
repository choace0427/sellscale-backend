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
    - SENT_OUTREACH: email has been sent
    - EMAIL_OPENED: email has been opened
    - ACCEPTED: email has been accepted (clicked on link)
    - ACTIVE_CONVO: email has been accepted and a conversation has been started
    - SCHEDULING: a is being scheduled following a conversation
    - DEMO_SET: a demo has been set
    - DEMO_WON: a demo has been won
    - DEMO_LOST: a demo has been lost
    """

    UNKNOWN = "UNKNOWN"
    NOT_SENT = "NOT_SENT"
    SENT_OUTREACH = "SENT_OUTREACH"

    EMAIL_OPENED = "EMAIL_OPENED"
    ACCEPTED = "ACCEPTED"
    ACTIVE_CONVO = "ACTIVE_CONVO"
    SCHEDULING = "SCHEDULING"

    NOT_INTERESTED = "NOT_INTERESTED"
    DEMO_SET = "DEMO_SET"

    DEMO_WON = "DEMO_WON"
    DEMO_LOST = "DEMO_LOST"

    def to_dict():
        return {
            "NOT_SENT": "Not Sent",
            "SENT_OUTREACH": "Sent email",
            "EMAIL_OPENED": "Opened Email",
            "ACCEPTED": "Accepted",
            "ACTIVE_CONVO": "Active Convo",
            "SCHEDULING": "Scheduling",
            "NOT_INTERESTED": "Not Interested",
            "DEMO_SET": "Demo Scheduled",
            "DEMO_WON": "Demo Complete",
            "DEMO_LOST": "Demo Missed",
        }


class ProspectEmail(db.Model):
    __tablename__ = "prospect_email"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    email_status = db.Column(db.Enum(ProspectEmailStatus), nullable=True)
    outreach_status = db.Column(db.Enum(ProspectEmailOutreachStatus), nullable=True)

    personalized_first_line = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")
    )

    date_sent = db.Column(db.DateTime, nullable=True)
    batch_id = db.Column(db.String, nullable=True)


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
    - OUTREACH: outreach interaction
    - SALESLOFT: salesloft interaction
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
