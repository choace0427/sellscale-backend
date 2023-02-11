from app import db
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
)
from .constants import SAMPLE_LINKEDIN_RESEARCH_PAYLOAD
from src.prospecting.services import (
    search_prospects,
    get_prospects,
    add_prospect,
    get_linkedin_slug_from_url,
    get_navigator_slug_from_url,
    add_prospects_from_json_payload,
    validate_prospect_json_payload,
    update_prospect_status,
    create_prospect_from_linkedin_link,
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
def test_search_prospects():
    c = basic_client()
    a = basic_archetype(c)
    c_sdr = basic_client_sdr(c)
    prospect = basic_prospect(c, a, c_sdr)  # Testing Testasara

    prospects = search_prospects(
        query="test", client_id=c.id, client_sdr_id=c_sdr.id, limit=10
    )
    assert len(prospects) == 1

    prospects = search_prospects(
        query="NO MATCH", client_id=c.id, client_sdr_id=c_sdr.id, limit=10
    )
    assert len(prospects) == 0


@use_app_context
def test_get_prospects():
    c = basic_client()
    a = basic_archetype(c)
    c_sdr = basic_client_sdr(c)
    prospect = basic_prospect(c, a, c_sdr, full_name="david", company="SellScale")
    prospect_2 = basic_prospect(c, a, c_sdr, full_name="adam", company="SellScale")
    prospect_3 = basic_prospect(c, a, c_sdr, full_name="ben", company="SellScale")

    filter_1 = [{
        "field": "full_name",
        "direction": 1              # 1 = ascending, -1 = descending
    }]
    prospects = get_prospects(c.id, c_sdr.id, limit=10, offset=0, filters=filter_1)
    assert len(prospects) == 3
    assert prospects[0].full_name == "adam"
    assert prospects[1].full_name == "ben"
    assert prospects[2].full_name == "david"

    prospect_4 = basic_prospect(c, a, c_sdr, full_name="adam", company="Apple")
    prospect_5 = basic_prospect(c, a, c_sdr, full_name="ben", company="Apple")
    filter_2 = [
        {
            "field": "full_name",
            "direction": 1              # 1 = ascending, -1 = descending
        },
        {
            "field": "company",
            "direction": 1              # 1 = ascending, -1 = descending
        }
    ]
    prospects = get_prospects(c.id, c_sdr.id, limit=10, offset=0, filters=filter_2)
    assert len(prospects) == 5
    assert prospects[0].full_name == "adam"
    assert prospects[0].company == "Apple"
    assert prospects[1].full_name == "adam"
    assert prospects[1].company == "SellScale"
    assert prospects[2].full_name == "ben"
    assert prospects[2].company == "Apple"
    assert prospects[3].full_name == "ben"
    assert prospects[3].company == "SellScale"
    assert prospects[4].full_name == "david"
    assert prospects[4].company == "SellScale"

    filter_3 = [
        {
            "field": "company",
            "direction": 1              # 1 = ascending, -1 = descending
        },
        {
            "field": "full_name",
            "direction": 1              # 1 = ascending, -1 = descending
        }
    ]
    prospects = get_prospects(c.id, c_sdr.id, limit=10, offset=0, filters=filter_3)
    assert len(prospects) == 5
    assert prospects[0].full_name == "adam"
    assert prospects[0].company == "Apple"
    assert prospects[1].full_name == "ben"
    assert prospects[1].company == "Apple"
    assert prospects[2].full_name == "adam"
    assert prospects[2].company == "SellScale"
    assert prospects[3].full_name == "ben"
    assert prospects[3].company == "SellScale"
    assert prospects[4].full_name == "david"
    assert prospects[4].company == "SellScale"

    prospect_6 = basic_prospect(c, a, c_sdr, full_name="jim", company="Apple", status=ProspectStatus.DEMO_SET)
    prospects = get_prospects(c.id, c_sdr.id, status=["DEMO_SET"], limit=10, offset=0, filters=filter_3)
    assert len(prospects) == 1
    assert prospects[0].full_name == "jim"


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
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].client_id == client_id
    assert prospects[0].archetype_id == archetype_id

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
        full_name="testing testoro",
        industry="saas",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].client_id == client_id
    assert prospects[0].archetype_id == archetype_id
    assert prospects[0].first_name == "Testing"
    assert prospects[0].last_name == "Testoro"

    client = Client.query.get(client_id)
    archetype2 = basic_archetype(client)
    archetype_id2 = archetype2.id
    add_prospect(client_id=client_id, archetype_id=archetype_id2)

    prospects = Prospect.query.order_by(Prospect.id.asc()).all()
    assert len(prospects) == 2
    assert prospects[1].archetype_id == archetype_id2

    assert archetype_id != archetype_id2

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        company="testing testasara",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing testoro",
        industry="saas",
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
        full_name="testing testoro",
        industry="saas",
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
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.apply_async")
@mock.patch(
    "src.prospecting.controllers.collect_and_run_celery_jobs_for_upload.apply_async"
)
def test_add_prospects_from_json_payload(
    collect_and_run_celery_jobs_for_upload_mock, mock_create_from_linkedin
):
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
            "email": "aakash.adesara@gmail.com",
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",  # duplicate
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan Sharma",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",  # duplicate
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan No Linkedin",
            "linkedin_url": "some_linkedin",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",  # no  email
            "full_name": "Ishan No Email",
            "linkedin_url": "another_linkedin",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",  # no  email
            "full_name": "",
            "linkedin_url": "final_linkedin",
            "title": "Growth Engineer",
        },
    ]
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client_id,
                "client_sdr_id": sdr_id,
                "archetype_id": archetype_id,
                "csv_payload": payload,
                "email_enabled": False,
            }
        ),
    )
    assert response.status_code == 200


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.apply_async")
@mock.patch(
    "src.prospecting.controllers.collect_and_run_celery_jobs_for_upload.apply_async"
)
@mock.patch("src.prospecting.services.add_prospect")
def test_add_2_prospects_from_csv(
    mock_add_prospect,
    mock_collect_and_run_celery_jobs_for_upload,
    mock_create_from_linkedin,
):
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
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client_id,
                "client_sdr_id": sdr_id,
                "archetype_id": archetype_id,
                "csv_payload": payload,
            }
        ),
    )
    assert response.status_code == 200

    prospects = Prospect.query.all()
    assert len(prospects) == 0
    assert mock_add_prospect.call_count == 0

    for i in prospects:
        assert i.company_url == "https://athelas.com/"


@use_app_context
def test_validate_prospect_json_payload_invalid():
    """
    Tests that a bad payload is rejected
    """
    bad_li_payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",
            "full_name": "Aakash Adesara",
            "linkedin_urlBAD": "",
            "title": "Growth Engineer",
        },
    ]
    validated, _ = validate_prospect_json_payload(
        payload=bad_li_payload, email_enabled=False
    )
    assert validated == False

    bad_email_payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "emailBAD": "",
            "full_name": "Aakash Adesara",
            "linkedin_url": "some_url",
            "title": "Growth Engineer",
        },
    ]
    validated, _ = validate_prospect_json_payload(
        payload=bad_email_payload, email_enabled=True
    )
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
    validated, _ = validate_prospect_json_payload(
        payload=correct_payload, email_enabled=True
    )
    assert validated == True


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.delay")
def test_add_prospects_from_json_payload_invalid(
    create_prospect_from_linkedin_link_patch,
):
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

    response = add_prospects_from_json_payload(client.id, archetype.id, payload)
    assert response == ("Success", 0)

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


@use_app_context
@mock.patch(
    "src.prospecting.services.research_personal_profile_details",
    return_value=SAMPLE_LINKEDIN_RESEARCH_PAYLOAD,
)
def test_create_prospect_from_linkedin_link(research_personal_profile_details_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    client_id = client.id
    archetype_id = archetype.id
    linkedin_url = "https://www.linkedin.com/in/johnny/"

    create_prospect_from_linkedin_link(
        archetype_id=archetype.id,
        url=linkedin_url,
        batch="123",
        email="johnny@sellscale.com",
    )

    prospect = Prospect.query.first()
    assert prospect.client_id == client_id
    assert prospect.archetype_id == archetype_id
    assert prospect.email == "johnny@sellscale.com"
    assert prospect.employee_count == "1001-5000"
    assert prospect.industry == "Information Technology & Services"
    assert prospect.linkedin_url == "linkedin.com/in/matthewdbarlow"
    assert (
        prospect.title
        == "Senior Manager - Global Sales Compensation & Administration at Sungard Availability Services"
    )
    assert (
        prospect.company_url
        == "https://www.linkedin.com/company/sungard-availability-services/"
    )
    assert prospect.company == "Sungard Availability Services"
    assert (
        "Highly successful, dependable, with a strong work ethic and noted leadership skills. Strategic minded with an eye to the optimal future state.  Experience in managing processes and systems, with background in Lean Six Sigma and Scrum. Organized and detail-oriented. Focused on benefiting the team dynamic and quality of work through effective communication and a high level of integrity."
        in prospect.linkedin_bio
    )
    assert prospect.first_name == "Matthew"
    assert prospect.last_name == "Barlow"
