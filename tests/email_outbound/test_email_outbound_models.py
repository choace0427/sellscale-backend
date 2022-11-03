from src.email_outbound.models import EmailCustomizedFieldTypes
from src.ml.models import GNLPModelType
from model_import import EmailSchema, ProspectEmail
from test_utils import (
    basic_client,
    basic_archetype,
    basic_gnlp_model,
    basic_prospect,
    basic_generated_message,
)
from decorators import use_app_context
from test_utils import test_app
from app import db


def test_email_field_types():
    email_customized_values = [e.value for e in EmailCustomizedFieldTypes]
    gnlp_values = [e.value for e in GNLPModelType]

    for e in email_customized_values:
        assert e in gnlp_values


@use_app_context
def test_email_schema():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)

    email_schema = EmailSchema(
        name="test",
        client_archetype_id=archetype.id,
        personalized_first_line_gnlp_model_id=gnlp_model.id,
    )
    db.session.add(email_schema)
    db.session.commit()

    all_schemas = EmailSchema.query.all()
    assert len(all_schemas) == 1


@use_app_context
def test_prospect_email():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)

    email_schema = EmailSchema(
        name="test",
        client_archetype_id=archetype.id,
        personalized_first_line_gnlp_model_id=gnlp_model.id,
    )
    db.session.add(email_schema)
    db.session.commit()

    all_schemas = EmailSchema.query.all()
    assert len(all_schemas) == 1

    prospect_email: ProspectEmail = ProspectEmail(
        email_schema_id=email_schema.id,
        prospect_id=prospect.id,
        personalized_first_line=generated_message.id,
    )
    db.session.add(prospect_email)
    db.session.commit()
    prospects = ProspectEmail.query.all()
    assert len(prospects) == 1
