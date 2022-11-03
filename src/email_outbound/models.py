from app import db
import enum


"""
Explanation
ClientArchetype -> client archetype
EmailSchema -> an email template (root). Each archetype can have multiple EmailSchema's
EmailCustomizedField -> a customized field in an EmailSchema
GeneratedMessage -> multiple generations can be made per custom field. 1 can be approved per custom field

You need to approve all the generated messages under GeneratedMessage for 
EmailCustomizedField -> EmailSchema to register and be eligible for send.

For actual send, we'll generate a CSV based on email_schema -> fields -> selected/approved messages
"""


class EmailSchema(db.Model):
    __tablename__ = "email_schema"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )


class EmailCustomizedField(db.Model):
    __tablename__ = "email_customized_field"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    email_schema_id = db.Column(
        db.Integer, db.ForeignKey("email_schema.id"), nullable=False
    )
