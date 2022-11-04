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
from src.email_outbound.models import EmailSchema, ProspectEmail, ProspectEmailStatus
from app import app
import json
import mock


def test_email_field_types():
    email_customized_values = [e.value for e in EmailCustomizedFieldTypes]
    gnlp_values = [e.value for e in GNLPModelType]

    for e in email_customized_values:
        assert e in gnlp_values


@use_app_context
def test_create_email_schema():
    client = basic_client()
    archetype = basic_archetype(client)

    response = app.test_client().post(
        "/email_generation/create_email_schema",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "name": "This is a test email schema",
                "client_archetype_id": archetype.id,
            }
        ),
    )
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"

    all_schemas = EmailSchema.query.all()
    assert len(all_schemas) == 1
    assert all_schemas[0].name == "This is a test email schema"


@use_app_context
@mock.patch("src.message_generation.services.generate_prospect_email.delay")
def test_create_prospect_email(generate_prospect_email_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    prospect_id: int = prospect.id
    personalized_first_line = basic_generated_message(prospect, gnlp_model)

    email_schema = create_email_schema(
        name="test",
        client_archetype_id=archetype.id,
    )

    response = app.test_client().post(
        "/email_generation/batch",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [prospect_id],
                "email_schema_id": email_schema.id,
            }
        ),
    )
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"
    assert generate_prospect_email_mock.call_count == 1
