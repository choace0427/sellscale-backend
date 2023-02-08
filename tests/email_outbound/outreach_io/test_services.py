from app import db
from decorators import use_app_context
from test_utils import (
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
    convert_outreach_payload_to_ss
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

    opened_payload = [{
        "Email": "test-email",
        "Sequence State": "Finished",
        "Emailed?": "Yes",
        "Opened?": "Yes",
        "Clicked?": "No",
        "Replied?": "No",
    }]
    sei_ss_id = convert_outreach_payload_to_ss(client_id, client_sdr_id, sei_raw_id, opened_payload)
    assert len(SalesEngagementInteractionSS.query.all()) == 1
    sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(sei_ss_id)
    assert sei_ss.client_id == client_id
    assert sei_ss.client_sdr_id == client_sdr_id
    assert sei_ss.sales_engagement_interaction_raw_id == sei_raw_id

    bounced_payload = [{
        "Email": "test-email",
        "Sequence State": "Bounced",
        "Emailed?": "No",
        "Opened?": "No",
        "Clicked?": "No",
        "Replied?": "No",
    }]
    sei_ss_id = convert_outreach_payload_to_ss(client_id, client_sdr_id, sei_raw_id, bounced_payload)
    assert len(SalesEngagementInteractionSS.query.all()) == 2
    sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(sei_ss_id)
    assert sei_ss.client_id == client_id
    assert sei_ss.client_sdr_id == client_sdr_id
    assert sei_ss.sales_engagement_interaction_raw_id == sei_raw_id

    ooo_payload = [{
        "Email": "test-email",
        "Sequence State": "Paused OOTO",
    }]
    sei_ss_id = convert_outreach_payload_to_ss(client_id, client_sdr_id, sei_raw_id, ooo_payload)
    assert len(SalesEngagementInteractionSS.query.all()) == 3
    sei_ss: SalesEngagementInteractionSS = SalesEngagementInteractionSS.query.get(sei_ss_id)
    assert sei_ss.client_id == client_id
    assert sei_ss.client_sdr_id == client_sdr_id
    assert sei_ss.sales_engagement_interaction_raw_id == sei_raw_id


# @use_app_context
# def test_update_status_from_csv_no_errors():
#     client = basic_client()
#     archetype = basic_archetype(client)
#     prospect = basic_prospect(client, archetype)
#     email_schema = basic_email_schema(archetype)
#     prospect.email = "test-email"
#     db.session.add(prospect)
#     db.session.commit()
#     prospect_email = basic_prospect_email(prospect, email_schema)
#     prospect_email_id = prospect_email.id
#     prospect_email.email_status = ProspectEmailStatus.SENT
#     db.session.add(prospect_email)
#     db.session.commit()
#     client_id = client.id

#     emailed_payload = [
#         {
#             "Email": "test-email",
#             "Sequence State": "Finished",
#             "Emailed?": "Yes",
#             "Opened?": "No",
#             "Clicked?": "No",
#             "Replied?": "No",
#         }
#     ]

#     validated, message = update_status_from_csv(emailed_payload, client.id)
#     prospect_email = ProspectEmail.query.filter_by(id=prospect_email_id).first()
#     prospect_email_id = prospect_email.id
#     assert validated
#     assert message == "Made updates to 1/1 prospects."
#     assert prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
#     prospect_email_status_record = ProspectEmailStatusRecords.query.filter_by(
#         prospect_email_id=prospect_email.id
#     ).all()
#     assert len(prospect_email_status_record) == 1
#     assert (
#         prospect_email_status_record[0].from_status
#         == ProspectEmailOutreachStatus.UNKNOWN
#     )
#     assert (
#         prospect_email_status_record[0].to_status
#         == ProspectEmailOutreachStatus.SENT_OUTREACH
#     )

#     opened_payload = [
#         {
#             "Email": "test-email",
#             "Sequence State": "Finished",
#             "Emailed?": "Yes",
#             "Opened?": "Yes",
#             "Clicked?": "No",
#             "Replied?": "No",
#         }
#     ]
#     validated, message = update_status_from_csv(opened_payload, client_id)
#     prospect_email = ProspectEmail.query.filter_by(id=prospect_email_id).first()
#     assert validated
#     assert message == "Made updates to 1/1 prospects."
#     assert prospect_email.outreach_status == ProspectEmailOutreachStatus.EMAIL_OPENED
#     prospect_email_status_record: ProspectEmailStatusRecords = (
#         ProspectEmailStatusRecords.query.filter_by(
#             prospect_email_id=prospect_email.id
#         ).all()
#     )
#     assert len(prospect_email_status_record) == 2
#     assert (
#         prospect_email_status_record[1].from_status
#         == ProspectEmailOutreachStatus.SENT_OUTREACH
#     )
#     assert (
#         prospect_email_status_record[1].to_status
#         == ProspectEmailOutreachStatus.EMAIL_OPENED
#     )

#     clicked_payload = [
#         {
#             "Email": "test-email",
#             "Sequence State": "Finished",
#             "Emailed?": "Yes",
#             "Opened?": "Yes",
#             "Clicked?": "Yes",
#             "Replied?": "No",
#         }
#     ]
#     validated, message = update_status_from_csv(clicked_payload, client_id)
#     prospect_email = ProspectEmail.query.filter_by(id=prospect_email_id).first()
#     assert validated
#     assert message == "Made updates to 1/1 prospects."
#     assert prospect_email.outreach_status == ProspectEmailOutreachStatus.ACCEPTED
#     prospect_email_status_record: ProspectEmailStatusRecords = (
#         ProspectEmailStatusRecords.query.filter_by(
#             prospect_email_id=prospect_email.id
#         ).all()
#     )
#     assert len(prospect_email_status_record) == 3
#     assert (
#         prospect_email_status_record[2].from_status
#         == ProspectEmailOutreachStatus.EMAIL_OPENED
#     )
#     assert (
#         prospect_email_status_record[2].to_status
#         == ProspectEmailOutreachStatus.ACCEPTED
#     )

#     replied_payload = [
#         {
#             "Email": "test-email",
#             "Sequence State": "Finished",
#             "Emailed?": "Yes",
#             "Opened?": "Yes",
#             "Clicked?": "Yes",
#             "Replied?": "Yes",
#         }
#     ]
#     validated, message = update_status_from_csv(replied_payload, client_id)
#     prospect_email = ProspectEmail.query.filter_by(id=prospect_email_id).first()
#     assert validated
#     assert message == "Made updates to 1/1 prospects."
#     assert prospect_email.outreach_status == ProspectEmailOutreachStatus.ACTIVE_CONVO
#     prospect_email_status_record: ProspectEmailStatusRecords = (
#         ProspectEmailStatusRecords.query.filter_by(
#             prospect_email_id=prospect_email.id
#         ).all()
#     )
#     assert len(prospect_email_status_record) == 4
#     assert (
#         prospect_email_status_record[3].from_status
#         == ProspectEmailOutreachStatus.ACCEPTED
#     )
#     assert (
#         prospect_email_status_record[3].to_status
#         == ProspectEmailOutreachStatus.ACTIVE_CONVO
#     )
#     # Note that we call this twice to test that we don't update records if the status is the same
#     validated, message = update_status_from_csv(replied_payload, client_id)
#     prospect_email = ProspectEmail.query.filter_by(id=prospect_email.id).first()
#     assert validated
#     assert message == "Made updates to 0/1 prospects."
#     assert prospect_email.outreach_status == ProspectEmailOutreachStatus.ACTIVE_CONVO
#     prospect_email_status_record: ProspectEmailStatusRecords = (
#         ProspectEmailStatusRecords.query.filter_by(
#             prospect_email_id=prospect_email_id
#         ).all()
#     )
#     assert len(prospect_email_status_record) == 4


# @use_app_context
# def test_update_status_from_csv_catch_errors():
#     client = basic_client()
#     archetype = basic_archetype(client)
#     prospect = basic_prospect(client, archetype)
#     email_schema = basic_email_schema(archetype)
#     prospect.email = "test-email"
#     db.session.add(prospect)
#     db.session.commit()
#     prospect_email = basic_prospect_email(prospect, email_schema)
#     prospect_email_id = prospect_email.id

#     empty_payload = []
#     validated, message = update_status_from_csv(empty_payload, client.id)
#     assert not validated
#     assert message == "No rows in payload"

#     not_finished_sequence_payload = [
#         {
#             "Email": "test-email",
#             "Sequence State": "NOT FINISHED",  # <--- not finished
#             "Emailed?": "Yes",
#             "Opened?": "Yes",
#             "Clicked?": "Yes",
#             "Replied?": "Yes",
#         }
#     ]
#     validated, message = update_status_from_csv(
#         not_finished_sequence_payload, client.id
#     )
#     assert validated
#     assert message == "Made updates to 0/1 prospects."
#     prospect_email = ProspectEmail.query.filter_by(id=prospect_email_id).first()
#     assert prospect_email.outreach_status == None
#     prospect_email_status_record: ProspectEmailStatusRecords = (
#         ProspectEmailStatusRecords.query.filter_by(
#             prospect_email_id=prospect_email.id
#         ).all()
#     )
#     assert len(prospect_email_status_record) == 0

#     no_prospect_payload = [
#         {
#             "Email": "non-existent-email",  # <--- no prospect for this meail
#             "Sequence State": "Finished",
#             "Emailed?": "Yes",
#             "Opened?": "Yes",
#             "Clicked?": "Yes",
#             "Replied?": "Yes",
#         }
#     ]
#     validated, message = update_status_from_csv(no_prospect_payload, client.id)
#     assert validated
#     assert (
#         message
#         == "Warning: Impartial write, the following emails were not found or not updatable: ['non-existent-email']"
#     )
#     assert prospect_email.outreach_status == None
#     prospect_email_status_record: ProspectEmailStatusRecords = (
#         ProspectEmailStatusRecords.query.filter_by(
#             prospect_email_id=prospect_email.id
#         ).all()
#     )
#     assert len(prospect_email_status_record) == 0

#     good_payload_no_update = [  # Note that this is a good payload. However, the ProspectEmail is in DRAFT status, not SENT.
#         {
#             "Email": "test-email",
#             "Sequence State": "Finished",
#             "Emailed?": "Yes",
#             "Opened?": "Yes",
#             "Clicked?": "Yes",
#             "Replied?": "Yes",
#         }
#     ]
#     validated, message = update_status_from_csv(good_payload_no_update, client.id)
#     assert validated
#     assert (
#         message
#         == "Warning: Impartial write, the following emails were not found or not updatable: ['test-email']"
#     )
#     assert prospect_email.email_status == ProspectEmailStatus.DRAFT
#     assert prospect_email.outreach_status == None
#     prospect_email_status_record: ProspectEmailStatusRecords = (
#         ProspectEmailStatusRecords.query.filter_by(
#             prospect_email_id=prospect_email.id
#         ).all()
#     )
#     assert len(prospect_email_status_record) == 0

#     prospect_email.email_status = ProspectEmailStatus.SENT
#     prospect_email.outreach_status = ProspectEmailOutreachStatus.SENT_OUTREACH
#     db.session.add(prospect_email)
#     db.session.commit()
#     bad_update_payload = [  # We cannot skip straight to "Replied?" if the prospect has not opened the email.
#         {
#             "Email": "test-email",
#             "Sequence State": "Finished",
#             "Emailed?": "Yes",
#             "Opened?": "No",
#             "Clicked?": "No",
#             "Replied?": "Yes",
#         }
#     ]
#     validated, message = update_status_from_csv(bad_update_payload, client.id)
#     assert validated
#     assert (
#         message
#         == "Warning: Impartial write, the following emails were not found or not updatable: ['test-email']"
#     )


# @use_app_context
# def test_get_new_status():
#     dict_replied = {"Replied?": "Yes"}
#     dict_clicked = {"Clicked?": "Yes"}
#     dict_opened = {"Opened?": "Yes"}
#     dict_emailed = {"Emailed?": "Yes"}
#     assert get_new_status(dict_replied) == ProspectEmailOutreachStatus.ACTIVE_CONVO
#     assert get_new_status(dict_clicked) == ProspectEmailOutreachStatus.ACCEPTED
#     assert get_new_status(dict_opened) == ProspectEmailOutreachStatus.EMAIL_OPENED
#     assert get_new_status(dict_emailed) == ProspectEmailOutreachStatus.SENT_OUTREACH
