from app import app, db
from tests.test_utils.test_utils import (
    basic_client,
    basic_archetype,
    basic_prospect,
    test_app,
    basic_client_sdr,
    basic_generated_message,
    basic_generated_message_cta,
    basic_prospect_email,
    basic_research_payload,
    get_login_token,
)
from model_import import (
    Prospect,
    ProspectStatus,
    ProspectNote,
    ProspectChannels,
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectOverallStatus,
    GeneratedMessage,
    ClientSDR,
)
from tests.test_utils.decorators import use_app_context
import json
import mock


@use_app_context
def test_search_prospects_endpoint():
    c = basic_client()
    a = basic_archetype(c)
    c_sdr = basic_client_sdr(c)
    p = basic_prospect(c, a, c_sdr)

    response = app.test_client().get(
        f"prospect/search?query=test&client_id={c.id}&client_sdr_id={c_sdr.id}&limit=10"
    )
    data = json.loads(response.data)
    assert len(data) == 1
    assert data.pop().get("id") == p.id
    assert response.status_code == 200

    response = app.test_client().get(
        f"prospect/search?query=notfound&client_id={c.id}&client_sdr_id={c_sdr.id}&limit=10"
    )
    data = json.loads(response.data)
    assert len(data) == 0
    assert response.status_code == 200


@use_app_context
def test_get_prospects():
    c = basic_client()
    a = basic_archetype(c)
    c_sdr = basic_client_sdr(c)
    prospect = basic_prospect(c, a, c_sdr, full_name="david", company="SellScale")
    prospect_2 = basic_prospect(c, a, c_sdr, full_name="adam", company="SellScale")
    prospect_3 = basic_prospect(c, a, c_sdr, full_name="ben", company="SellScale")

    unauthenticated_response = app.test_client().post(
        "prospect/get_prospects",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": c.id,
                "client_sdr_id": c_sdr.id,
            }
        ),
    )
    assert unauthenticated_response.status_code == 401

    response = app.test_client().post(
        "prospect/get_prospects",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps(
            {
                "client_id": c.id,
                "client_sdr_id": c_sdr.id,
            }
        ),
    )
    assert response.json.get("total_count") == 3
    assert response.status_code == 200

    prospect_4 = basic_prospect(c, a, c_sdr, full_name="adam", company="Apple")

    response = app.test_client().post(
        "prospect/get_prospects",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps(
            {"client_id": c.id, "client_sdr_id": c_sdr.id, "query": "adam"}
        ),
    )
    assert response.json.get("total_count") == 2
    assert response.status_code == 200

    response = app.test_client().post(
        "prospect/get_prospects",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps(
            {
                "client_id": c.id,
                "client_sdr_id": c_sdr.id,
                "query": "adam",
                "ordering": [
                    {"field": "company", "direction": 1}
                ],  # ORDER BY company_name ASC
            }
        ),
    )
    assert response.json.get("total_count") == 2
    assert response.json.get("prospects")[0].get("company") == "Apple"
    assert response.status_code == 200

    bad_filters_response = app.test_client().post(
        "prospect/get_prospects",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps(
            {
                "client_id": c.id,
                "client_sdr_id": c_sdr.id,
                "query": "adam",
                "ordering": [{"bad_key": "bad_field", "direction": 1}],
            }
        ),
    )
    assert bad_filters_response.status_code == 400
    assert bad_filters_response.json.get("message") == "Invalid filters supplied to API"


@use_app_context
def test_patch_update_status_endpoint():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.RESPONDED
    prospect_email = basic_prospect_email(prospect)
    prospect_email_id = prospect_email.id

    # Test that the prospect status is updated for LINKEDIN
    response = app.test_client().patch(
        f"prospect/{prospect_id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps(
            {
                "channel_type": ProspectChannels.LINKEDIN.value,
                "new_status": ProspectStatus.ACTIVE_CONVO.value,
            }
        ),
    )
    assert response.status_code == 200
    p: Prospect = Prospect.query.get(prospect_id)
    assert p.status == ProspectStatus.ACTIVE_CONVO
    assert p.overall_status == ProspectOverallStatus.ACTIVE_CONVO

    # Test that the prospect status is updated for EMAIL
    # Also tests that the prospect overall status is updated
    response = app.test_client().patch(
        f"prospect/{prospect_id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps(
            {
                "channel_type": ProspectChannels.EMAIL.value,
                "new_status": ProspectEmailOutreachStatus.DEMO_SET.value,
            }
        ),
    )
    print(response.text)
    assert response.status_code == 200
    p: Prospect = Prospect.query.get(prospect_id)
    assert p.status == ProspectStatus.ACTIVE_CONVO
    pe: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    assert pe.outreach_status == ProspectEmailOutreachStatus.DEMO_SET
    assert p.overall_status == ProspectOverallStatus.DEMO


@use_app_context
def test_patch_update_status_endpoint_failed():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.PROSPECTED
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().patch(
        f"prospect/{prospect_id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps(
            {
                "channel_type": ProspectChannels.LINKEDIN.value,
                "new_status": ProspectStatus.DEMO_SET.value,
            }
        ),
    )
    assert response.status_code == 400
    p: Prospect = Prospect.query.get(prospect_id)
    assert p.status == ProspectStatus.PROSPECTED


@use_app_context
@mock.patch(
    "src.prospecting.controllers.create_prospect_from_linkedin_link.apply_async"
)
def test_post_prospect_from_link(create_prospect_from_linkedin_link_patch):
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)

    response = app.test_client().post(
        "prospect/from_link",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
        data=json.dumps({"archetype_id": archetype.id, "url": "some_linkedin_url"}),
    )
    assert response.status_code == 200
    create_prospect_from_linkedin_link_patch.call_count == 1


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.delay")
def test_post_prospect_from_link_chain(create_prospect_from_linkedin_link_patch):
    client = basic_client()
    archetype = basic_archetype(client)

    response = app.test_client().post(
        "prospect/from_link_chain",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "archetype_id": archetype.id,
                "url_string": "some_linkedin_url...some_other_url",
            }
        ),
    )
    assert response.status_code == 200
    assert create_prospect_from_linkedin_link_patch.call_count == 2


# @use_app_context
# @mock.patch("src.prospecting.services.match_prospect_as_sent_outreach.delay")
# def test_post_batch_mark_sent(match_prospect_as_sent_outreach_patch):
#     client = basic_client()
#     archetype = basic_archetype(client)
#     prospect1 = basic_prospect(client, archetype)
#     prospect2 = basic_prospect(client, archetype)
#     prospect1_id = prospect1.id
#     prospect2_id = prospect2.id
#     prospect_ids = [prospect1_id, prospect2_id]
#     client_sdr = basic_client_sdr(client)
#     client_sdr_id = client_sdr.id

#     response = app.test_client().post(
#         "prospect/batch_mark_sent",
#         headers={"Content-Type": "application/json"},
#         data=json.dumps({"prospect_ids": prospect_ids, "client_sdr_id": client_sdr_id}),
#     )
#     assert response.status_code == 200
#     assert match_prospect_as_sent_outreach_patch.call_count == 2


@use_app_context
def test_post_add_note():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id

    response = app.test_client().post(
        "prospect/add_note",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "prospect_id": prospect_id,
                "note": "some note",
            }
        ),
    )
    assert response.status_code == 200
    notes: ProspectNote = ProspectNote.query.filter_by(prospect_id=prospect_id).all()
    assert len(notes) == 1

    nonexistent_response = app.test_client().post(
        "prospect/add_note",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "prospect_id": prospect_id + 1,
                "note": "some note",
            }
        ),
    )
    assert nonexistent_response.status_code == 404
    assert nonexistent_response.json.get("message") == "Prospect not found"

    client_sdr_2 = basic_client_sdr(client)
    client_sdr_2.auth_token = "some_token"
    db.session.add(client_sdr_2)
    db.session.commit()
    prospect_2 = basic_prospect(client, archetype, client_sdr_2)
    nonauthorized_response = app.test_client().post(
        "prospect/add_note",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "prospect_id": prospect_2.id,
                "note": "some note",
            }
        ),
    )
    assert nonauthorized_response.status_code == 403
    assert (
        nonauthorized_response.json.get("message") == "Prospect does not belong to user"
    )


@use_app_context
def test_post_batch_mark_as_lead():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    assert not prospect.is_lead

    response = app.test_client().post(
        "prospect/batch_mark_as_lead",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "id": prospect_id,
                        "is_lead": False,
                    }
                ]
            }
        ),
    )
    assert response.status_code == 200

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.is_lead == False

    response = app.test_client().post(
        "prospect/batch_mark_as_lead",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "id": prospect_id,
                        "is_lead": True,
                    }
                ]
            }
        ),
    )
    assert response.status_code == 200

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.is_lead == True


@use_app_context
def test_get_prospect_details():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id

    rp = basic_research_payload(prospect)

    response = app.test_client().get(
        f"prospect/{prospect_id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert response.status_code == 200
    assert response.json.get("message") == "Success"

    no_prospect_response = app.test_client().get(
        f"prospect/{prospect_id + 1}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert no_prospect_response.status_code == 404
    assert no_prospect_response.json.get("message") == "Prospect not found"

    prospect = basic_prospect(client, archetype)
    unauthorized_response = app.test_client().get(
        f"prospect/{prospect.id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert unauthorized_response.status_code == 403
    assert (
        unauthorized_response.json.get("message")
        == "This prospect does not belong to you"
    )


@use_app_context
def test_get_valid_channel_types():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)

    prospect_id = prospect.id

    response = app.test_client().get(
        "prospect/get_valid_channel_types?prospect_id={prospect_id}".format(
            prospect_id=prospect_id
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert response.status_code == 200
    assert response.json == {"choices": []}

    gm = basic_generated_message(prospect)
    gm_id = gm.id

    prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = gm_id
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().get(
        "prospect/get_valid_channel_types?prospect_id={prospect_id}".format(
            prospect_id=prospect_id
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert response.status_code == 200
    assert response.json == {"choices": [{"label": "Linkedin", "value": "LINKEDIN"}]}

    email = basic_prospect_email(prospect)
    email_id = email.id

    prospect = Prospect.query.get(prospect_id)
    prospect.approved_prospect_email_id = email_id
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().get(
        "prospect/get_valid_channel_types?prospect_id={prospect_id}".format(
            prospect_id=prospect_id
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert response.status_code == 200
    assert response.json == {
        "choices": [
            {"label": "Linkedin", "value": "LINKEDIN"},
            {"label": "Email", "value": "EMAIL"},
        ]
    }


@use_app_context
def test_get_valid_next_prospect_statuses_endpoint():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id

    # LinkedIn
    linkedin_response = app.test_client().get(
        f"prospect/{prospect_id}/get_valid_next_statuses?channel_type=LINKEDIN",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert linkedin_response.status_code == 200
    assert len(linkedin_response.json["valid_next_statuses"]) == 3
    assert (
        linkedin_response.json["valid_next_statuses"][
            ProspectStatus.QUEUED_FOR_OUTREACH.value
        ]
        is not None
    )
    assert (
        linkedin_response.json["valid_next_statuses"][
            ProspectStatus.SENT_OUTREACH.value
        ]
        is not None
    )
    assert (
        linkedin_response.json["valid_next_statuses"][
            ProspectStatus.NOT_QUALIFIED.value
        ]
        is not None
    )

    assert len(linkedin_response.json["all_statuses"]) == 19

    # Another LinkedIn
    prospect.status = ProspectStatus.ACCEPTED
    linkedin_another_response = app.test_client().get(
        f"prospect/{prospect_id}/get_valid_next_statuses?channel_type=LINKEDIN",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert linkedin_another_response.status_code == 200
    assert len(linkedin_another_response.json["valid_next_statuses"]) == 3
    assert (
        linkedin_another_response.json["valid_next_statuses"][
            ProspectStatus.RESPONDED.value
        ]
        is not None
    )
    assert (
        linkedin_another_response.json["valid_next_statuses"][
            ProspectStatus.ACTIVE_CONVO.value
        ]
        is not None
    )
    assert (
        linkedin_another_response.json["valid_next_statuses"][
            ProspectStatus.NOT_QUALIFIED.value
        ]
        is not None
    )
    assert len(linkedin_another_response.json["all_statuses"]) == 19

    # Email
    prospect_email = basic_prospect_email(prospect)
    prospect.approved_prospect_email_id = prospect_email.id
    email_response = app.test_client().get(
        f"prospect/{prospect_id}/get_valid_next_statuses?channel_type=EMAIL",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert email_response.status_code == 200
    assert len(email_response.json["valid_next_statuses"]) == 2
    assert (
        email_response.json["valid_next_statuses"][
            ProspectEmailOutreachStatus.SENT_OUTREACH.value
        ]
        is not None
    )
    assert (
        email_response.json["valid_next_statuses"][
            ProspectEmailOutreachStatus.NOT_SENT.value
        ]
        is not None
    )
    assert len(email_response.json["all_statuses"]) == 13

    # Another Email
    prospect_email.outreach_status = ProspectEmailOutreachStatus.ACTIVE_CONVO
    email_another_response = app.test_client().get(
        f"prospect/{prospect_id}/get_valid_next_statuses?channel_type=EMAIL",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert email_another_response.status_code == 200
    assert len(email_another_response.json["valid_next_statuses"]) == 2
    print(email_another_response.json["valid_next_statuses"])
    assert (
        email_another_response.json["valid_next_statuses"][
            ProspectEmailOutreachStatus.SCHEDULING.value
        ]
        is not None
    )
    assert (
        email_another_response.json["valid_next_statuses"][
            ProspectEmailOutreachStatus.NOT_INTERESTED.value
        ]
        is not None
    )
    assert len(email_another_response.json["all_statuses"]) == 13


@use_app_context
def test_remove_prospect_from_contact_list():
    client = basic_client()
    client_archetype = basic_archetype(client)
    client_sdr: ClientSDR = basic_client_sdr(client)
    prospect = basic_prospect(
        client=client,
        archetype=client_archetype,
        client_sdr=client_sdr,
    )
    prospect_id = prospect.id
    prospect.overall_status = ProspectOverallStatus.ACCEPTED
    db.session.add(prospect)
    db.session.commit()

    assert prospect.client_sdr_id == client_sdr.id

    response = app.test_client().post(
        f"prospect/remove_from_contact_list?prospect_id={prospect_id}".format(
            prospect_id=prospect_id
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200

    prospect = Prospect.query.get(prospect_id)
    assert prospect.overall_status == ProspectOverallStatus.REMOVED
