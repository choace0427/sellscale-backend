from app import db
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_sei_raw,
)
from src.email_outbound.models import (
    SalesEngagementInteractionSS,
)
from src.email_outbound.outreach_io.services import (
    validate_outreach_csv_payload,
    convert_outreach_payload_to_ss,
)


@use_app_context
def test_validate_outreach_csv_payload():
    good_payload = [
        {
            "Email": "test-email",
            "Sequence State": "test-sequence-state",
            "Emailed?": "test-emailed",
            "Opened?": "test-opened",
            "Clicked?": "test-clicked",
            "Replied?": "test-replied",
            "Finished": "test-finished",
        },
    ]

    bad_payload = [
        {
            "Email": "test-email",
            "Clicked?": "test-clicked",
            "Replied?": "test-replied",
        }
    ]

    validated, message = validate_outreach_csv_payload(good_payload)
    assert validated
    assert message == "OK"

    validated, message = validate_outreach_csv_payload(bad_payload)
    assert not validated

    validated, message = validate_outreach_csv_payload([])
    assert not validated
    assert message == "No rows in payload"


@use_app_context
def test_convert_outreach_payload():
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    sei_raw = basic_sei_raw(client, client_sdr)
    sei_raw_id = sei_raw.id

    opened_payload = [
        {
            "Email": "test-email",
            "Sequence State": "Finished",
            "Emailed?": "Yes",
            "Opened?": "Yes",
            "Clicked?": "No",
            "Replied?": "No",
        }
    ]
    sei_ss_id = convert_outreach_payload_to_ss(
        client_id, client_sdr_id, sei_raw_id, opened_payload
    )
    assert len(SalesEngagementInteractionSS.query.all()) == 1
    sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(
        sei_ss_id
    )
    assert sei_ss.client_id == client_id
    assert sei_ss.client_sdr_id == client_sdr_id
    assert sei_ss.sales_engagement_interaction_raw_id == sei_raw_id

    bounced_payload = [
        {
            "Email": "test-email",
            "Sequence State": "Bounced",
            "Emailed?": "No",
            "Opened?": "No",
            "Clicked?": "No",
            "Replied?": "No",
        }
    ]
    sei_ss_id = convert_outreach_payload_to_ss(
        client_id, client_sdr_id, sei_raw_id, bounced_payload
    )
    assert len(SalesEngagementInteractionSS.query.all()) == 2
    sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(
        sei_ss_id
    )
    assert sei_ss.client_id == client_id
    assert sei_ss.client_sdr_id == client_sdr_id
    assert sei_ss.sales_engagement_interaction_raw_id == sei_raw_id

    ooo_payload = [
        {
            "Email": "test-email",
            "Sequence State": "Paused OOTO",
        }
    ]
    sei_ss_id = convert_outreach_payload_to_ss(
        client_id, client_sdr_id, sei_raw_id, ooo_payload
    )
    assert len(SalesEngagementInteractionSS.query.all()) == 3
    sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(
        sei_ss_id
    )
    assert sei_ss.client_id == client_id
    assert sei_ss.client_sdr_id == client_sdr_id
    assert sei_ss.sales_engagement_interaction_raw_id == sei_raw_id
