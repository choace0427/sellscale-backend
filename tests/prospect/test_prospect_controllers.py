from app import app, db
from test_utils import (
    basic_client,
    basic_archetype,
    basic_prospect,
    test_app,
    basic_client_sdr,
    basic_generated_message,
    basic_gnlp_model,
    basic_prospect_email,
    basic_research_payload,
    get_login_token,
)
from src.prospecting.services import match_prospect_as_sent_outreach
from model_import import Prospect, ProspectStatus, ProspectNote
from decorators import use_app_context
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
@mock.patch("src.prospecting.services.calculate_prospect_overall_status.delay")
def test_patch_update_status_endpoint(calculate_prospect_overall_status):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.RESPONDED
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().patch(
        "prospect/",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id, "new_status": "ACTIVE_CONVO"}),
    )
    assert response.status_code == 200
    p: Prospect = Prospect.query.get(prospect_id)
    assert p.status == ProspectStatus.ACTIVE_CONVO


@use_app_context
def test_patch_update_status_endpoint_failed():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.PROSPECTED
    db.session.add(prospect)
    db.session.commit()

    response = app.test_client().patch(
        "prospect/",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id, "new_status": "DEMO_SET"}),
    )
    assert response.status_code == 400
    p: Prospect = Prospect.query.get(prospect_id)
    assert p.status == ProspectStatus.PROSPECTED


@use_app_context
@mock.patch("src.prospecting.controllers.create_prospect_from_linkedin_link.delay")
def test_post_prospect_from_link(create_prospect_from_linkedin_link_patch):
    client = basic_client()
    archetype = basic_archetype(client)

    response = app.test_client().post(
        "prospect/from_link",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"archetype_id": archetype.id, "url": "some_linkedin_url"}),
    )
    assert response.status_code == 200
    create_prospect_from_linkedin_link_patch.assert_called_once_with(
        archetype_id=archetype.id, url="some_linkedin_url", batch=mock.ANY
    )


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


@use_app_context
@mock.patch("src.prospecting.services.match_prospect_as_sent_outreach.delay")
def test_post_batch_mark_sent(match_prospect_as_sent_outreach_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect1 = basic_prospect(client, archetype)
    prospect2 = basic_prospect(client, archetype)
    prospect1_id = prospect1.id
    prospect2_id = prospect2.id
    prospect_ids = [prospect1_id, prospect2_id]
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    response = app.test_client().post(
        "prospect/batch_mark_sent",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_ids": prospect_ids, "client_sdr_id": client_sdr_id}),
    )
    assert response.status_code == 200
    assert match_prospect_as_sent_outreach_patch.call_count == 2


@use_app_context
def test_post_add_note():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    response = app.test_client().post(
        "prospect/add_note",
        headers={"Content-Type": "application/json"},
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
@mock.patch("src.prospecting.services.calculate_prospect_overall_status.delay")
def test_get_prospect_details(calculate_prospect_overall_status_patch):
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

    response = app.test_client().get(
        "prospect/get_valid_next_prospect_statuses?prospect_id={prospect_id}&channel_type=LINKEDIN".format(
            prospect_id=prospect_id
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    assert response.status_code == 200
    assert response.json == {
        "NOT_QUALIFIED": "Not Qualified",
        "SENT_OUTREACH": "Sent Outreach",
    }


@use_app_context
def test_get_valid_channel_types():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    gnlp_model = basic_gnlp_model(archetype)
    gm = basic_generated_message(prospect, gnlp_model)
    email = basic_prospect_email(prospect)
    gm_id = gm.id
    email_id = email.id

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
    assert response.json == {"choices": [{"label": "Linkedin", "value": "Linkedin"}]}

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
            {"label": "Linkedin", "value": "Linkedin"},
            {"label": "Email", "value": "Linkedin"},
        ]
    }
