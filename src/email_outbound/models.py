from app import db
import enum


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


class ProspectEmail(db.Model):
    __tablename__ = "prospect_email"

    id = db.Column(db.Integer, primary_key=True)
    email_schema_id = db.Column(
        db.Integer, db.ForeignKey("email_schema.id"), nullable=False
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    email_status = db.Column(db.Enum(ProspectEmailStatus), nullable=True)
    outreach_status = db.Column(db.Enum(ProspectEmailOutreachStatus), nullable=True)

    personalized_first_line = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")
    )

    date_sent = db.Column(db.DateTime, nullable=True)
    batch_id = db.Column(db.String, nullable=True)


class ProspectEmailStatusRecords(db.Model):
    """ Records the status changes of a prospect_email """
    __tablename__ = "prospect_email_status_records"

    id = db.Column(db.Integer, primary_key=True)
    prospect_email_id = db.Column(db.Integer, db.ForeignKey("prospect_email.id"))
    from_status = db.Column(db.Enum(ProspectEmailOutreachStatus), nullable=False)
    to_status = db.Column(db.Enum(ProspectEmailOutreachStatus), nullable=False)
