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

    personalized_first_line_gnlp_model_id = db.Column(
        db.Integer, db.ForeignKey("gnlp_models.id"), nullable=True
    )


class ProspectEmail(db.Model):
    __tablename__ = "prospect_email"

    id = db.Column(db.Integer, primary_key=True)
    email_schema_id = db.Column(
        db.Integer, db.ForeignKey("email_schema.id"), nullable=False
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)

    personalized_first_line = db.Column(
        db.Integer, db.ForeignKey("generated_message.id")
    )


# create schema
#   write test
# generate email from schema + prospect IDs
#   for prospect id in prospect ids
#        create schema with schema id + prospect id
#            generate first line, etc etc
#            sav to email
#            TODO ProspectEmailMessageStatus
#            set status to DRAFT

# approve email
#        approve underlying generated message IDs
#        approve email ProspectEmail

# send email
#        mark prospectEmail as set
#        mark underlying generated messages as sent
