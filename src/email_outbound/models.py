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


class ProspectEmail(db.Model):
    __tablename__ = "prospect_email"

    id = db.Column(db.Integer, primary_key=True)
    email_schema_id = db.Column(
        db.Integer, db.ForeignKey("email_schema.id"), nullable=False
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    email_status = db.Column(db.Enum(ProspectEmailStatus), nullable=True)

    personalized_first_line = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")
    )

    date_sent = db.Column(db.DateTime, nullable=True)
    batch_id = db.Column(db.String, nullable=True)
