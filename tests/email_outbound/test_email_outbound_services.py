from src.email_outbound.models import EmailCustomizedFieldTypes
from src.ml.models import GNLPModelType
from src.email_outbound.services import create_email_schema, create_prospect_email
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
from src.email_outbound.models import EmailSchema, ProspectEmail, ProspectEmailStatus


def test_email_field_types():
    email_customized_values = [e.value for e in EmailCustomizedFieldTypes]
    gnlp_values = [e.value for e in GNLPModelType]

    for e in email_customized_values:
        assert e in gnlp_values


@use_app_context
def test_create_email_schema():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)

    email_schema = create_email_schema(
        name="test",
        client_archetype_id=archetype.id,
    )

    all_schemas = EmailSchema.query.all()
    assert len(all_schemas) == 1
    assert all_schemas[0].name == "test"


@use_app_context
def test_create_prospect_email():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    personalized_first_line = basic_generated_message(prospect, gnlp_model)

    email_schema = create_email_schema(
        name="test",
        client_archetype_id=archetype.id,
    )

    prospect_email = create_prospect_email(
        email_schema_id=email_schema.id,
        prospect_id=prospect.id,
        personalized_first_line_id=personalized_first_line.id,
        batch_id="123123123",
    )
    assert prospect_email.email_schema_id == email_schema.id
    assert prospect_email.prospect_id == prospect.id
    assert prospect_email.personalized_first_line == personalized_first_line.id
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT
    assert prospect_email.batch_id == "123123123"

    all_prospect_emails = ProspectEmail.query.all()
    assert len(all_prospect_emails) == 1
    assert all_prospect_emails[0].email_schema_id == email_schema.id
    assert all_prospect_emails[0].prospect_id == prospect.id
    assert all_prospect_emails[0].personalized_first_line == personalized_first_line.id
    assert all_prospect_emails[0].email_status == ProspectEmailStatus.DRAFT
    assert all_prospect_emails[0].batch_id == "123123123"
