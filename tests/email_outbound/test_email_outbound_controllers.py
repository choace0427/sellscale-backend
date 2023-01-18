from app import db
from src.email_outbound.models import EmailCustomizedFieldTypes
from model_import import GeneratedMessage
from src.ml.models import GNLPModelType
from src.email_outbound.services import create_email_schema, create_prospect_email
from test_utils import (
    basic_client,
    basic_archetype,
    basic_gnlp_model,
    basic_prospect,
    basic_generated_message,
    basic_email_schema,
    basic_prospect_email
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


@use_app_context
def test_post_batch_update_emails():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    prospect_id: int = prospect.id
    personalized_first_line = basic_generated_message(prospect, gnlp_model)
    personalized_first_line.completion = "original"
    db.session.add(personalized_first_line)
    db.session.commit()

    email_schema = create_email_schema(
        name="test",
        client_archetype_id=archetype.id,
    )

    prospect_email = create_prospect_email(
        email_schema_id=email_schema.id,
        prospect_id=prospect_id,
        personalized_first_line_id=personalized_first_line.id,
        batch_id=1,
    )
    prospect.approved_prospect_email_id = prospect_email.id
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().post(
        "/email_generation/batch_update_emails",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "prospect_id": prospect.id,
                        "personalized_first_line": "this is a test",
                    }
                ]
            }
        ),
    )
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"

    all_prospect_emails = ProspectEmail.query.all()
    assert len(all_prospect_emails) == 1
    personalized_first_line_id = all_prospect_emails[0].personalized_first_line
    personalized_first_line = GeneratedMessage.query.get(personalized_first_line_id)
    assert personalized_first_line.completion == "this is a test"


@use_app_context
def test_post_batch_update_emails_failed():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp_model = basic_gnlp_model(archetype)
    prospect = basic_prospect(client, archetype)
    prospect_id: int = prospect.id
    personalized_first_line = basic_generated_message(prospect, gnlp_model)
    personalized_first_line.completion = "original"
    db.session.add(personalized_first_line)
    db.session.commit()

    email_schema = create_email_schema(
        name="test",
        client_archetype_id=archetype.id,
    )

    prospect_email = create_prospect_email(
        email_schema_id=email_schema.id,
        prospect_id=prospect_id,
        personalized_first_line_id=personalized_first_line.id,
        batch_id=1,
    )
    prospect.approved_prospect_email_id = prospect_email.id
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().post(
        "/email_generation/batch_update_emails",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "prospect_id": prospect.id,
                    }
                ]
            }
        ),
    )
    assert response.status_code == 400
    assert (
        response.data.decode("utf-8")
        == "Personalized first line missing in one of the rows"
    )

    all_prospect_emails = ProspectEmail.query.all()
    assert len(all_prospect_emails) == 1
    personalized_first_line_id = all_prospect_emails[0].personalized_first_line
    personalized_first_line = GeneratedMessage.query.get(personalized_first_line_id)
    assert personalized_first_line.completion == "original"

    response = app.test_client().post(
        "/email_generation/batch_update_emails",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "personalized_first_line": "this is a test",
                    }
                ]
            }
        ),
    )
    assert response.status_code == 400
    assert response.data.decode("utf-8") == "Prospect ID missing in one of the rows"

    all_prospect_emails = ProspectEmail.query.all()
    assert len(all_prospect_emails) == 1
    personalized_first_line_id = all_prospect_emails[0].personalized_first_line
    personalized_first_line = GeneratedMessage.query.get(personalized_first_line_id)
    assert personalized_first_line.completion == "original"


@use_app_context
@mock.patch("src.email_outbound.controllers.update_status_from_csv", return_value=(True, "OK"))
@mock.patch("src.email_outbound.controllers.validate_outreach_csv_payload", return_value=(True, "OK"))
def test_update_status_from_csv_payload(validate_payload_mock, update_status_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    email_schema = basic_email_schema(archetype)
    prospect.email = "test-email"
    db.session.add(prospect)
    db.session.commit()
    prospect_email = basic_prospect_email(prospect, email_schema)
    prospect_email.email_status = ProspectEmailStatus.SENT
    db.session.add(prospect_email)
    db.session.commit()

    response = app.test_client().post(
        "/email_generation/update_status/csv",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "csv_payload": [
                    {
                        "Email": "test-email",
                        "Sequence State": "Finished",
                        "Emailed?": "Yes",
                        "Opened?": "No",
                        "Clicked?": "No",
                        "Replied?": "No",
                    }
                ],
                "client_id": client.id,
            }
        ),
    )
    assert response.status_code == 200
    assert validate_payload_mock.call_count == 1
    assert validate_payload_mock.called_with(
        csv_payload=[
                    {
                        "Email": "test-email",
                        "Sequence State": "Finished",
                        "Emailed?": "Yes",
                        "Opened?": "No",
                        "Clicked?": "No",
                        "Replied?": "No",
                    }
                ]
    )
    assert update_status_mock.call_count == 1
    assert update_status_mock.called_with(
        csv_payload=[
            {
                "Email": "test-email",
                "Sequence State": "Finished",
                "Emailed?": "Yes",
                "Opened?": "No",
                "Clicked?": "No",
                "Replied?": "No",
            }
        ],
        client_id=client.id,
    )
