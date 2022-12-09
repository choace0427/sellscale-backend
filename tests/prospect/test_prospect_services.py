from app import db
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
)
from src.prospecting.services import (
    add_prospect,
    get_linkedin_slug_from_url,
    get_navigator_slug_from_url,
    add_prospects_from_json_payload,
    validate_prospect_json_payload,
    update_prospect_status,
)
from model_import import (
    Prospect,
    ProspectStatusRecords,
    Prospect,
    ProspectUploadBatch,
    Client,
    ProspectStatus,
    ProspectNote,
)
from decorators import use_app_context
import mock
import src.utils.slack
from app import app
import json


@use_app_context
def test_update_prospect_status_with_note():
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].client_id == client_id
    assert prospects[0].archetype_id == archetype_id
    assert prospects[0].batch == "123"

    prospect0 = prospects[0]
    prospect_id = prospect0.id
    update_prospect_status(
        prospect_id=prospect0.id,
        new_status=ProspectStatus.SENT_OUTREACH,
        note="testing",
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect is not None
    assert prospect.status == ProspectStatus.SENT_OUTREACH

    notes: list = ProspectNote.query.all()
    assert len(notes) == 1
    assert notes[0].prospect_id == prospect_id
    assert notes[0].note == "testing"


@use_app_context
def test_update_prospect_status_active_convo_disable_ai():
    client = basic_client()
    archetype = basic_archetype(client)
    add_prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    prospect0 = prospects[0]
    prospect0.status = ProspectStatus.RESPONDED
    db.session.add(prospect0)
    db.session.commit()

    update_prospect_status(
        prospect_id=prospect0.id,
        new_status=ProspectStatus.ACTIVE_CONVO,
        note="testing",
    )
    prospect = Prospect.query.get(prospect0.id)
    assert prospect is not None
    assert prospect.deactivate_ai_engagement == None

    client2 = basic_client()
    archetype2 = basic_archetype(client2)
    archetype2.disable_ai_after_prospect_engaged = True
    add_prospect(
        client_id=client2.id,
        archetype_id=archetype2.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2
    prospect1 = prospects[1]
    prospect1.status = ProspectStatus.RESPONDED
    db.session.add(prospect1)
    db.session.commit()

    update_prospect_status(
        prospect_id=prospect1.id,
        new_status=ProspectStatus.ACTIVE_CONVO,
        note="testing",
    )
    prospect = Prospect.query.get(prospect1.id)
    assert prospect is not None
    assert prospect.deactivate_ai_engagement == True


@use_app_context
def test_add_prospect():
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].client_id == client_id
    assert prospects[0].archetype_id == archetype_id
    assert prospects[0].batch == "123"

    client = Client.query.get(client_id)
    archetype2 = basic_archetype(client)
    archetype_id2 = archetype2.id
    add_prospect(client_id=client_id, archetype_id=archetype_id2, batch="456")

    prospects = Prospect.query.order_by(Prospect.id.asc()).all()
    assert len(prospects) == 2
    assert prospects[1].batch == "456"
    assert prospects[1].archetype_id == archetype_id2

    assert archetype_id != archetype_id2

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url="12381",
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing sara",  # new name here
        industry="saas",
        batch="123",
        linkedin_url="12381",
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 3


@use_app_context
def test_get_linkedin_slug_from_url():
    urls = [
        "https://www.linkedin.com/in/testingsara",
        "www.linkedin.com/in/testingsara",
        "linkedin.com/in/testingsara",
        "https://www.linkedin.com/in/testingsara/?testing=123",
        "www.linkedin.com/in/testingsara/?testing=123",
        "linkedin.com/in/testingsara/?testing=123",
        "linkedin.com/in/testingsara?testing=123",
    ]

    for url in urls:
        slug = get_linkedin_slug_from_url(url)
        assert slug == "testingsara"


@use_app_context
def test_get_sales_nav_slug_from_url():
    urls = [
        "https://www.linkedin.com/sales/lead/testingsara",
        "www.linkedin.com/sales/lead/testingsara",
        "linkedin.com/sales/lead/testingsara",
    ]

    for url in urls:
        slug = get_navigator_slug_from_url(url)
        assert slug == "testingsara"


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.delay")
@mock.patch("src.prospecting.services.add_prospect.delay")
def test_add_prospects_from_json_payload(mock_add_prospect, mock_create_from_linkedin):
    payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",  # duplicate shouldn't add
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan Sharma",  # different name
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan No Linkedin",  # no linkeidn
            "linkedin_url": "",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",  # no  email
            "full_name": "Ishan No Email",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",  # no  email
            "full_name": "",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
    ]
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client_id,
                "archetype_id": archetype_id,
                "csv_payload": payload,
            }
        ),
    )
    assert response.status_code == 200

    batches: list = ProspectUploadBatch.query.all()
    assert len(batches) == 1

    batch_0: ProspectUploadBatch = batches[0]
    assert batch_0.archetype_id == archetype_id
    assert batch_0.num_prospects == 5

    prospects = Prospect.query.all()
    assert len(prospects) == 0
    assert mock_add_prospect.call_count == 1
    assert mock_create_from_linkedin.call_count == 4

    for i in prospects:
        assert i.company_url == "https://athelas.com/"


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.delay")
@mock.patch("src.prospecting.services.add_prospect.delay")
def test_add_2_prospects_from_csv(mock_add_prospect, mock_create_from_linkedin):
    payload = [
        {
            "First Name": "Suzanne",
            "Last Name": "Cooner",
            "State": "Iowa",
            "full_name": "Suzanne Cooner",
            "company": "Audubon County Memorial Hospital",
            "title": "Chief Executive Officer",
            "linkedin_url": "https://www.linkedin.com/in/suzanne-cooner-31849321",
        },
        {
            "First Name": "Michelle",
            "Last Name": "Rebelsky",
            "State": "Iowa",
            "full_name": "Michelle Rebelsky",
            "company": "Audubon County Memorial Hospital",
            "title": "Chief Medical Officer",
            "linkedin_url": "https://www.linkedin.com/in/michelle-rebelsky-md-mba-609702143",
        },
    ]

    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client_id,
                "archetype_id": archetype_id,
                "csv_payload": payload,
            }
        ),
    )
    assert response.status_code == 200

    batches: list = ProspectUploadBatch.query.all()
    assert len(batches) == 1

    batch_0: ProspectUploadBatch = batches[0]
    assert batch_0.archetype_id == archetype_id
    assert batch_0.num_prospects == 2

    prospects = Prospect.query.all()
    assert len(prospects) == 0
    assert mock_add_prospect.call_count == 0
    assert mock_create_from_linkedin.call_count == 2

    for i in prospects:
        assert i.company_url == "https://athelas.com/"


@use_app_context
def test_validate_prospect_json_payload_invalid():
    """
    Tests that a bad payload is rejected
    """
    bad_email_li_payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "emailBAD": "",
            "full_name": "Aakash Adesara",
            "linkedin_urlBAD": "",
            "title": "Growth Engineer",
        },
    ]
    validated, _ = validate_prospect_json_payload(bad_email_li_payload)
    assert validated == False

    correct_payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "some_email",
            "full_name": "Aakash Adesara",
            "linkedin_url": "some_url",
            "title": "Growth Engineer",
        },
    ]
    validated, _ = validate_prospect_json_payload(correct_payload)
    assert validated == True


@use_app_context
def test_add_prospects_from_json_payload_invalid():
    payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",
            "full_name": "Aakash Adesara",
            "linkedin_url": "",
            "title": "Growth Engineer",
        },
    ]
    client = basic_client()
    archetype = basic_archetype(client)

    success, couldnt_add = add_prospects_from_json_payload(
        client.id, archetype.id, payload
    )
    assert success == False
    assert couldnt_add == ["Aakash Adesara"]

    prospects = Prospect.query.all()
    assert len(prospects) == 0


@use_app_context
def test_toggle_ai_engagement_endpoint():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    assert not prospect.deactivate_ai_engagement

    response = app.test_client().post(
        "prospect/toggle_ai_engagement",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200

    prospect = Prospect.query.get(prospect_id)
    assert prospect is not None
    assert prospect.deactivate_ai_engagement == True


@use_app_context
def test_delete_prospect_by_id_endpoint():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    response = app.test_client().delete(
        "prospect/delete_prospect",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect.id) is None


@use_app_context
def test_reengage_accepted_prospected():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.ACCEPTED

    response = app.test_client().post(
        "prospect/mark_reengagement",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect.id) is not None
    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.status == ProspectStatus.RESPONDED
    assert prospect.last_reviewed is not None
    assert prospect.times_bumped == 1

    response = app.test_client().post(
        "prospect/mark_reengagement",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect.id) is not None
    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.times_bumped == 2


@use_app_context
def test_reengage_active_prospected():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.ACTIVE_CONVO

    response = app.test_client().post(
        "prospect/mark_reengagement",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect.id) is not None
    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.status == ProspectStatus.ACTIVE_CONVO
    assert prospect.last_reviewed is not None


@use_app_context
@mock.patch("src.prospecting.services.send_slack_message")
def test_send_slack_reminder(send_slack_message_patch):
    client = basic_client()
    client.id = 1
    client.pipeline_notifications_webhook_url = "some_c_webhook"
    client_sdr = basic_client_sdr(client)
    client_sdr.id = 1
    client_sdr.pipeline_notifications_webhook_url = "some_sdr_webhook"
    archetype = basic_archetype(client)
    archetype.id = 1
    prospect = basic_prospect(client, archetype)
    prospect.id = 1
    prospect.client_id = 1
    prospect.client_sdr_id = 1
    prospect.li_last_message_from_prospect = "Last Message Test"
    prospect.li_conversation_thread_id = "some_url"
    db.session.commit()

    response = app.test_client().post(
        "prospect/send_slack_reminder",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": 1, "alert_reason": "test alert reason"}),
    )
    assert response.status_code == 200

    assert send_slack_message_patch is src.prospecting.services.send_slack_message
    assert send_slack_message_patch.call_count == 1

    prospect: Prospect = Prospect.query.get(1)
    assert prospect.last_reviewed is not None
    assert prospect.deactivate_ai_engagement == True
