from app import db
from src.email_outbound.models import EmailCustomizedFieldTypes
from model_import import GeneratedMessage, GeneratedMessageType
from src.email_outbound.services import create_prospect_email
from tests.test_utils.test_utils import (
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_generated_message,
    basic_prospect_email,
    basic_outbound_campaign,
)
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import test_app
from src.email_outbound.models import (
    EmailSchema,
    ProspectEmail,
    ProspectEmailStatus,
    SalesEngagementInteractionRaw,
)
from app import app
import json
import mock


@use_app_context
def test_post_batch_update_emails():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id: int = prospect.id
    outbound_campaign = basic_outbound_campaign(
        [prospect_id], GeneratedMessageType.EMAIL, archetype, sdr
    )
    personalized_first_line = basic_generated_message(prospect)
    personalized_first_line.completion = "original"
    db.session.add(personalized_first_line)
    db.session.commit()

    prospect_email = ProspectEmail(
        prospect_id=prospect_id,
        personalized_first_line=personalized_first_line.id,
        outbound_campaign_id=outbound_campaign.id,
    )
    db.session.add(prospect_email)
    db.session.commit()
    prospect.approved_prospect_email_id = prospect_email.id
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

    all_prospect_emails: list[ProspectEmail] = ProspectEmail.query.all()
    assert len(all_prospect_emails) == 1
    print(all_prospect_emails[0].personalized_first_line)
    personalized_first_line_id = all_prospect_emails[0].personalized_first_line


@use_app_context
def test_post_batch_update_emails_failed():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id: int = prospect.id
    outbound_campaign = basic_outbound_campaign(
        [prospect_id], GeneratedMessageType.EMAIL, archetype, sdr
    )
    personalized_first_line = basic_generated_message(prospect)
    personalized_first_line.completion = "original"
    db.session.add(personalized_first_line)
    db.session.commit()

    prospect_email = create_prospect_email(
        prospect_id=prospect_id,
        personalized_first_line_id=personalized_first_line.id,
        outbound_campaign_id=outbound_campaign.id,
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

    all_prospect_emails: list[ProspectEmail] = ProspectEmail.query.all()
    assert len(all_prospect_emails) == 1
    personalized_first_line_id = all_prospect_emails[0].personalized_first_line
    assert personalized_first_line_id is None

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
    assert personalized_first_line_id is None


@use_app_context
@mock.patch(
    "src.email_outbound.controllers.convert_outreach_payload_to_ss.apply_async",
    return_value=1,
)
@mock.patch(
    "src.email_outbound.controllers.collect_and_update_status_from_ss_data.s",
    return_value=True,
)
def test_update_status_from_csv_payload(collect_and_update_mock, convert_to_ss_mock):
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_email = basic_prospect_email(prospect)

    response = app.test_client().post(
        "/email_generation/update_status/csv",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "csv_payload": [
                    {
                        "Email": "test@email.com",
                        "Sequence State": "Finished",
                        "Sequence Name": "test-sequence",
                        "Emailed?": "Yes",
                        "Opened?": "No",
                        "Clicked?": "No",
                        "Replied?": "No",
                    }
                ],
                "client_id": client.id,
                "client_archetype_id": archetype.id,
                "client_sdr_id": sdr.id,
                "payload_source": "OUTREACH",
            }
        ),
    )
    assert response.status_code == 200
    assert response.data == b"Status update is in progress"
    assert SalesEngagementInteractionRaw.query.count() == 1
    se = SalesEngagementInteractionRaw.query.first()
    assert convert_to_ss_mock.called_once()
    assert convert_to_ss_mock.called_with(args=[se.id], link=collect_and_update_mock)
    assert collect_and_update_mock.called_once()
    assert collect_and_update_mock.called_with(1)


@use_app_context
@mock.patch(
    "src.email_outbound.controllers.batch_mark_prospects_in_email_campaign_queued",
    return_value="something",
)
def test_batch_mark_sent(batch_mark_mock):
    response = app.test_client().post(
        "/email_generation/batch/mark_sent",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": "1",
            }
        ),
    )

    assert response.status_code == 200
    assert response.data == b"OK"
    assert batch_mark_mock.called_once()
    assert batch_mark_mock.called_with(1)
